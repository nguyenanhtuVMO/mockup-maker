from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Thiết lập cấu hình kết nối đến cơ sở dữ liệu MySQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://username:password@localhost/database_name'
db = SQLAlchemy(app)

# Định nghĩa một bảng User cho lưu trữ thông tin người dùng
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

# Tạo cơ sở dữ liệu (chạy một lần để tạo bảng)
db.create_all()

new_user = User(username='new_user', password='new_password', is_admin=False)
db.session.add(new_user)
db.session.commit()
