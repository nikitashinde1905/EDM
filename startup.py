import os

import generate_code
from utilities.config_util import ConfigUtil

from flask import flash
from flask import render_template, Flask, request, redirect, url_for, send_from_directory, session

from werkzeug.utils import secure_filename
from uml_parser.parse_dm_file import Analyzer as p

from flask_pymongo import PyMongo
import bcrypt


ana = p()
config = ConfigUtil()

UPLOAD_FOLDER = 'input'
ALLOWED_EXTENSIONS = set(['xml'])

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# set MongoDB details
app.config['MONGO_DBNAME'] = config.get('Mongo_DB', 'db_name')
app.config['MONGO_URI'] = config.get('Mongo_DB', 'mongo_db_uri')
mongo = PyMongo(app)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    if 'username' in session:
        return render_template('upload_xml.html')
    return render_template('homepage.html')


@app.route('/login', methods=['POST'])
def login():
    users = mongo.db.users
    login_user = users.find_one({'username' : request.form['uname']})

    if login_user:
        if bcrypt.hashpw(request.form['psw'].encode('utf-8'), login_user['password'].encode('utf-8')) == login_user['password'].encode('utf-8'):
            session['username'] = request.form['uname']
            return redirect(url_for('index'))
    return 'Invalid username/password combination'

@app.route('/register', methods=['POST'])
def register():
    users = mongo.db.users
    existing_user = users.find_one({'username' : request.form['uname']})

    if existing_user is None:
        hashpass = bcrypt.hashpw(request.form['psw'].encode('utf-8'), bcrypt.gensalt())
        users.insert({'username' : request.form['uname'], 'password' : hashpass, 'email' : request.form['email']})
        session['username'] = request.form['uname']
        return redirect(url_for('index'))
    
    return 'That username already exists!'



@app.route('/result', methods=['GET', 'POST'])
def result():
    filename_str = ""
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filename_str = filename.split(".")[0]
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    #Parse XML and generate JSON
    ana.DM_File_Analyze('input', {'DM_Input_type': "Simple_XML"}, filename_str)

    #Parse JSON and generate code
    element_names, server_url = generate_code.generate_all(filename_str)

    print element_names
    print server_url

    #Convert collection names to dictionary for ID to name mapping
    dict_mapping = {}
    id = 1

    for element in element_names:
        dict_mapping[id] = [element, element_names[element]]
        id+=1

    print dict_mapping

    #Pass required data to the template
    description_data = {"collection_names":dict_mapping, "db_name":filename_str}
    description_data["server_url"] = server_url

    print description_data

    #Render the template
    return render_template('result_page.html', **description_data)

@app.route('/generated_code/<path:path>')
def generated_code(path):
    return send_from_directory('generated_code', path)

@app.route('/logout')
def logout():
   # remove the username from the session if it is there
   session.pop('username', None)
   return redirect(url_for('index'))

if __name__ == '__main__':
    
    host = config.get('Application', 'host')
    port = config.getInt('Application', 'port')
    app.secret_key = 'mysecret'
    app.run(host=host, port=port)