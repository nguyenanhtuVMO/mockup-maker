from flask import Flask, render_template, request, send_from_directory, send_file, make_response, url_for, session, redirect
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from PIL import Image
from datetime import datetime, timedelta
import requests
import os
import piexif
import csv
import random
import string

app = Flask(__name__)
app.secret_key = 'blueZ'  # Khóa bí mật cho session

# Khởi tạo đối tượng LoginManager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Đường dẫn để lưu trữ ảnh đầu ra
UPLOAD_FOLDER = "uploaded_images"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


class User(UserMixin):
    def __init__(self, id, username, password, role):
        self.id = id
        self.username = username
        self.password = password
        self.role = role


users = [
    User(id=1, username='user1', password='password1', role='user'),
    User(id=2, username='admin', password='admin', role='admin'),
]

# Hàm callback để load người dùng từ ID
@login_manager.user_loader
def load_user(user_id):
    for user in users:
        if user.id == int(user_id):
            return user
    return None

@app.route("/", methods=["GET", "POST"])

def index():
    # Kiểm tra xem người dùng đã đăng nhập hay chưa
    if not current_user.is_authenticated:
        return render_template("login.html")

    # Kiểm tra vai trò của người dùng
    if current_user.role == 'user':
        return render_template("index.html")
    elif current_user.role == 'admin':
        return render_template("admin_dashboard.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # Xác thực người dùng (thay thế bằng cơ sở dữ liệu thực)
        for user in users:
            if user.username == username and user.password == password:
                login_user(user)
                return render_template("index.html")

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route("/overlay", methods=["GET", "POST"])
def overlay():
    images = []  
    csv_filename = ""  
    if request.method == "POST":
        # Nhận các thông số từ để tạo Mockup từ Website
        x = int(request.form["x"])
        y = int(request.form["y"])
        scale_percent = float(request.form["scale-percent"])
        rotation = float(request.form["rotation"])
        width = int(request.form["width"])
        height = width
        output_format = request.form["output-format"]  

        # Nhận các value của metadata từ Website
        author = request.form["author"]
        copyright = request.form["copyright"]
        date_taken_option = request.form.get("date-taken-option")

        # Nhận khoảng thời gian từ biểu mẫu web
        start_datetime = request.form.get("start_datetime")
        end_datetime = request.form.get("end_datetime")

        # Nhận các value cho file CSV từ Website
        custom_filename = request.form["custom_filename"]
        price = request.form["price"]
        categories = request.form["categories"]
        image_data_list = []
        # Xử lý file ảnh
        background_files = request.files.getlist("background")
        overlay_files = request.files.getlist("overlay")

        if background_files and overlay_files:
            output_folder = os.path.join(app.config["UPLOAD_FOLDER"], "output")
            os.makedirs(output_folder, exist_ok=True)

            background_paths = [os.path.join(app.config["UPLOAD_FOLDER"], file.filename) for file in background_files]
            overlay_paths = [os.path.join(app.config["UPLOAD_FOLDER"], file.filename) for file in overlay_files]

            for file, path in zip(background_files + overlay_files, background_paths + overlay_paths):
                file.save(path)

            # Overlay images và nhận số lượng ảnh đã tạo ra
            number_of_images = overlay_images(
                background_paths, overlay_paths, output_folder, (x, y), scale_percent, rotation, width, height, output_format,
                price=request.form["price"],
                categories=request.form["categories"],
                custom_filename=custom_filename,
                author=author,
                copyright=copyright,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                image_data_list=image_data_list
            )

            # Collect paths to the generated images
            image_paths = [os.path.join(output_folder, file) for file in os.listdir(output_folder)]
            images.extend(image_paths)

            # Set the CSV filename after processing all images
            csv_filename = custom_filename

            # Create metadata for the images (date_taken)
            add_metadata_to_folder(output_folder, author, copyright, number_of_images, start_datetime, end_datetime)
            
        return render_template("result.html", images=images, csv_download_link=f"/download-csv/{csv_filename}")
    
    return redirect(url_for('index'))
    
def overlay_images(background_paths, overlay_paths, output_folder, position, scale_percent, rotation, width, height, output_format, price, categories, custom_filename, author, copyright, start_datetime, end_datetime, image_data_list):
    image_data_list = []  # Create a list to collect image data
    number_of_images = 0  # Initialize the number of images counter
    
    base_url = "tool.nizedoo.com/uploaded_images/output/"

    for background_path in background_paths:
        # Tải background
        background = Image.open(background_path)

        # Lặp qua từng tệp design và tạo mockup
        for overlay_path in overlay_paths:
            overlay = Image.open(overlay_path)

            # Lấy kích thước gốc của ảnh background
            background_width, background_height = background.size

            scale = scale_percent / 100.0
            
            # Scale design theo kích thước gốc của ảnh background
            new_width = int(overlay.width * scale)
            new_height = int(overlay.height * scale)
            overlay = overlay.resize((new_width, new_height))
                
            # Xoay design (nếu cần)
            overlay = overlay.rotate(rotation, expand=True)

            # Đảm bảo ảnh design có chế độ màu RGBA
            if overlay.mode != 'RGBA':
                overlay = overlay.convert('RGBA')

            # Xác định vị trí của design trên background (vị trí tuyệt đối)
            x_position = position[0]  # Lấy vị trí x tuyệt đối
            y_position = position[1]  # Lấy vị trí y tuyệt đối

            # Tạo một background mới với kích thước gốc và paste overlay lên đó
            new_background = Image.new('RGBA', (background_width, background_height))
            new_background.paste(background, (0, 0))
            new_background.paste(overlay, (x_position, y_position), overlay)

            # Chuyển đổi ảnh sang chế độ màu RGB trước khi lưu dưới định dạng JPEG
            new_background = new_background.convert('RGB')

            # Resize ảnh đầu ra theo kích thước đã nhập từ người dùng
            if width and height:
                new_background = new_background.resize((width, height))
            elif width:
                wpercent = (width / float(new_background.width))
                hsize = int((float(new_background.height) * float(wpercent)))
                new_background = new_background.resize((width, hsize), Image.ANTIALIAS)
            elif height:
                hpercent = (height / float(new_background.height))
                wsize = int((float(new_background.width) * float(hpercent)))
                new_background = new_background.resize((wsize, height), Image.ANTIALIAS)

            # Tạo tên cho ảnh đầu ra dựa trên tên overlay và background
            background_filename = os.path.basename(background_path)
            overlay_filename = os.path.basename(overlay_path)
            output_filename = f"{overlay_filename.split('.')[0]}_{background_filename.split('.')[0]}"

            # Xác định định dạng đầu ra
            output_extension = output_format if output_format in ["jpg", "webp"] else "jpg"  # Mặc định là JPEG nếu không có lựa chọn nào

            # Lưu ảnh kết quả vào thư mục lưu trữ
            output_path = os.path.join(output_folder, f"{output_filename}.{output_extension}")
            output_url = f"{base_url}{output_filename}.{output_extension}"
            new_background.save(output_path)
            
            # Tải ảnh từ URL và lưu nó vào đường dẫn cục bộ
            response = requests.get(output_url)
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    f.write(response.content)

            # Tạo SKU ngẫu nhiên (chuỗi chữ và số)
            sku = generate_random_sku()

            # Tạo dữ liệu cho tệp CSV và thêm vào list
            image_data = {
                "sku": sku, "name": output_filename, "price": price, "categories": categories, "image": output_url
            }

            # Add the 'count_default' and 'rating' columns to image_data
            count_default = random.randint(1, 80)
            rating = count_default * 2
            image_data["count_default"] = count_default
            image_data["rating"] = rating

            image_data_list.append(image_data)
            number_of_images += 1  # Tăng số lượng ảnh đã tạo

            # Chuyển giá trị start_datetime và end_datetime thành kiểu datetime và cập nhật Exif cho ảnh
            manipulate_exif(output_path, author, copyright, title=output_filename, subject=output_filename, custom_date_taken=generate_random_datetime(start_datetime, end_datetime))
        # Create a CSV file with custom_filename
    create_csv(output_folder, image_data_list, custom_filename)
    return number_of_images

    
    
# Hàm để gen random datetime
def generate_random_datetime(start_datetime, end_datetime):
    # Chuyển đổi thời gian đầu vào thành đối tượng datetime
    start_dt = datetime.strptime(start_datetime, "%Y-%m-%dT%H:%M:%S")
    end_dt = datetime.strptime(end_datetime, "%Y-%m-%dT%H:%M:%S")

    # Tạo thời gian ngẫu nhiên trong khoảng giữa start_dt và end_dt
    random_dt = start_dt + timedelta(seconds=random.randint(0, int((end_dt - start_dt).total_seconds())))

    # Chuyển đổi đối tượng datetime thành chuỗi YYYY:MM:DD HH:mm:ss
    random_datetime = random_dt.strftime("%Y:%m:%d %H:%M:%S")

    return random_datetime

def manipulate_exif(img_path, author, copyright, title, subject, custom_date_taken):
    img = Image.open(img_path)

    # Đảm bảo rằng hình ảnh có Exif data
    if 'exif' in img.info:
        exif_dict = piexif.load(img.info['exif'])
    else:
        exif_dict = {}

    # Tạo một mục '0th' nếu nó không tồn tại
    if '0th' not in exif_dict:
        exif_dict['0th'] = {}

    # Format thông tin author, copyright, title sang dạng bytes
    author_bytes = author.encode('utf-8')
    copyright_bytes = copyright.encode('utf-8')
    title_bytes = title.encode('utf-8')

    # Kiểm tra và thiết lập giá trị mặc định cho subject nếu nó là rỗng
    if not subject:
        subject = title
    subject_bytes = subject.encode('utf-8')

    # add hoặc update các trường Exif
    exif_dict['0th'][piexif.ImageIFD.Artist] = author_bytes
    exif_dict['0th'][piexif.ImageIFD.Copyright] = copyright_bytes
    exif_dict['0th'][piexif.ImageIFD.ImageDescription] = title_bytes
    exif_dict['0th'][piexif.ImageIFD.XPSubject] = subject_bytes
    exif_dict['0th'][piexif.ImageIFD.Rating] = 5  # Đặt Rating mặc định là 5

    # Thêm thông tin "Date taken" nếu có giá trị custom_date_taken
    if custom_date_taken:
        exif_dict['Exif'] = {
            piexif.ExifIFD.DateTimeOriginal: custom_date_taken,
            piexif.ExifIFD.DateTimeDigitized: custom_date_taken,
        }
    exif_bytes = piexif.dump(exif_dict)
    img.save(img_path, 'jpeg', exif=exif_bytes)

# Hàm để add metadata
def add_metadata_to_folder(input_folder, author, copyright, number_of_images, start_datetime, end_datetime):
    # Lặp qua tất cả các file hình ảnh trong input folder
    for filename in os.listdir(input_folder):
        if filename.endswith(('.jpg', '.jpeg', '.JPG', '.JPEG', '.webp')):
            img_path = os.path.join(input_folder, filename)

            # Tách tên file và bỏ đuôi định dạng ảnh
            title = os.path.splitext(filename)[0]
            subject = os.path.splitext(filename)[0]

            # Chuyển giá trị start_datetime và end_datetime thành kiểu datetime và cập nhật Exif cho ảnh
            manipulate_exif(img_path, author, copyright, title, subject, generate_random_datetime(start_datetime, end_datetime))

# Hàm để gen SKU
def generate_random_sku(length=8):
    # Tạo một chuỗi ngẫu nhiên gồm chữ cái và số
    characters = string.ascii_letters + string.digits
    sku = ''.join(random.choice(characters) for _ in range(length))
    return sku

# Hàm để tạo file CSV
def create_csv(output_folder, data, custom_filename):
    # Create full path cho file CSV dùng custom filename
    csv_path = os.path.join(output_folder, f"{custom_filename}.csv")

    # Viết data cho file CSV
    with open(csv_path, "w", newline="") as csvfile:
        fieldnames = ["sku", "name", "price", "categories", "image", "count_default", "rating"]  # Include the new columns
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()  # Write CSV header

        for item in data:
            writer.writerow(item)  # Write data to CSV file

@app.route("/download-csv/<csv_filename>", methods=["GET"])
def download_csv(csv_filename):
    # Define folder để lưu file CSV
    csv_folder = os.path.join(app.config["UPLOAD_FOLDER"], "output")

    # Create full path tới file CSV
    csv_file_path = os.path.join(csv_folder, f"{csv_filename}.csv")

    # Check if the CSV file exists
    if not os.path.exists(csv_file_path):
        return "File CSV không tồn tại", 404

    # Open the CSV file for reading
    with open(csv_file_path, "rb") as csv_file:
        csv_data = csv_file.read()

    # Set the response headers for CSV download
    response = make_response(csv_data)
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = f"attachment; filename={csv_filename}.csv"

    return response

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    output_folder = os.path.join(app.config["UPLOAD_FOLDER"], "output")
    return send_from_directory(output_folder, filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0",port="8080",debug=True)
