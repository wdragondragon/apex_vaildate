import os
from datetime import datetime

from flask import Flask, request, jsonify, send_file
from sqlalchemy import create_engine, Table, MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import select

from check import FileHashUtil
from model.FileHash import FileHash

app = Flask(__name__)

# 创建数据库引擎
# 这里假设你的MySQL服务器在localhost，数据库名是mydatabase，用户名是myuser，密码是mypassword
# 根据你的实际情况修改这个URL
# 从环境变量获取数据库连接信息
db_user = os.getenv('ag_db_user')
db_psw = os.getenv('ag_db_psw')
db_add = os.getenv('ag_db_add')
# 创建数据库连接
engine = create_engine(f'mysql+mysqlconnector://{db_user}:{db_psw}@{db_add}/ag')
# 反射数据库元数据
metadata = MetaData()
metadata.reflect(bind=engine)

# 获取对应的表
# 这里假设你的表名是`machines`
machines = Table('ag_machines', metadata, autoload_with=engine)


@app.route('/validate', methods=['POST'])
def validate():
    machine_code = request.form.get('machine_code')

    if not machine_code:
        return jsonify({"error": "机器码未提供"}), 400

    # 查询数据库
    with engine.connect() as connection:
        query = select(machines).where(machines.c.machine_code == machine_code)
        result = connection.execute(query)
        machine = result.fetchone()

        # 如果找到了对应的机器码，那么返回权限字段
        if machine is not None:
            if machine.access_granted and not is_expired(machine.expiration_time):
                return jsonify({"access_granted": 1})
            else:
                return jsonify({"access_granted": 0, "error": "授权已过期"}), 400
        # 如果没有找到对应的机器码，那么添加新的记录，并设置access_granted为False
        print("没有找到对应的机器码，添加新的记录")
        new_machine = machines.insert().values(machine_code=machine_code, access_granted=0)
        connection.execute(new_machine)
        connection.commit()
    # 如果没有找到对应的机器码，那么不允许运行程序
    return jsonify({"access_granted": 0})


def is_expired(expiration_time):
    return expiration_time is None or datetime.utcnow() > expiration_time


@app.route('/refresh_files', methods=['GET'])
def refresh_files():
    file_hashes = FileHashUtil.scan_directory('./apex_gun')
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        session.query(FileHash).delete()
        insert_list = [
            FileHash(file_path=file_path, file_hash=file_hash)
            for file_path, file_hash in file_hashes.items()
        ]
        session.add_all(insert_list)
        session.commit()
    except Exception as e:
        session.rollback()
        print("Error: ", e)
    finally:
        session.close()
    return 'ok'


@app.route('/filehashes', methods=['GET'])
def get_filehashes():
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        # 获取所有的 FileHash 对象
        file_hashes = session.query(FileHash).all()

        # 创建一个字典，其中包含所有的 file_paths 和对应的 hashes
        results = {fh.file_path: fh.file_hash for fh in file_hashes}

        return jsonify(results)
    except Exception as e:
        return str(e), 500
    finally:
        session.close()


@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    file_path = file.filename
    directory = os.path.dirname(file_path)

    # 如果目录不存在，创建目录
    if not os.path.exists(directory):
        os.makedirs(directory)

    file.save(file_path)
    return 'File uploaded successfully', 200


@app.route('/download', methods=['POST'])
def download_file():
    file_path = request.form.get('path')
    file_path = file_path.replace('./', '')
    print(file_path)
    return send_file(file_path, as_attachment=True)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8123)
