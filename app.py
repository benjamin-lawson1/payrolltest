# : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : Set Up Application

# . . . import Flask
from flask import Flask, render_template, request, redirect, url_for, make_response
from datetime import datetime
import random

# . . . import ability to perform background tasks
from concurrent.futures import ThreadPoolExecutor


# . . . import SQL Alchemy for Databases
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import and_

# . . . import email capabilities
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# . . . import for csv exporting
from io import StringIO
import csv

# . . . allows app to run 1 thread in the background
executor = ThreadPoolExecutor(2)

# . . . identify the application
app = Flask(__name__)

# : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : Create Databases

# . . . set up SQL database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
#app.config['SQLALCHEMY_DATABASE_URI'] = 'postgres://ihbtkzvmffptlm:49c545ef7f0eb46f93a14d6b600368da8ca380e24e93533327180ce8d16404ae@ec2-3-93-160-246.compute-1.amazonaws.com:5432/d5k1qki4ju7jgo'
db = SQLAlchemy(app)

# . . . add db: Users (id, name, email, pin)
class Users(db.Model):

    id = db.Column(db.Integer, unique=True, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    pin = db.Column(db.Integer, unique=True, nullable=False)
    type = db.Column(db.String(80), unique=False, nullable=False)
    confirmed = db.Column(db.Integer, unique=False, nullable=False)

# . . . add db: History (id,name,start,end,report)
class History(db.Model):

    id = db.Column(db.Integer, unique=True, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    start = db.Column(db.DateTime)
    end = db.Column(db.DateTime, nullable = True)
    report = db.Column(db.String(300), unique=False, nullable=True)

# : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : Create Routes

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - Home Screen
@app.route("/<int:user_pin>")
def home(user_pin,selected_user=None):
    
    # . . . if db is empty, create default users
    if Users.query.first() == None:
        
        # . . . create list, append users, add to db
        new_users = []
        
        new_users.append(Users(name='Benjamin',email='Benjamin@KiawahIslandGetaways.com',pin='2222',type='admin',confirmed=1))
        new_users.append(Users(name='Shawn',email='BenjaminLawson4@gmail.com',pin='1111',type='manager',confirmed=1))
        
        for user in new_users:
            db.session.add(user)
        
        db.session.commit()

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ Collect Data

    # . . determine the manager pin, admin pin
    global manager_pin
    global admin_pin
    manager_pin = 1111
    admin_pin = 22222
    #manager_pin = (Users.query.filter_by(type = 'manager').first()).pin
    #admin_pin = (Users.query.filter_by(type = 'admin').first()).pin
    
    # . . . generate greeting
    global greeting
    hour = datetime.now().hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 18:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ Forward to Page

    # . . . show admin page
    if user_pin == admin_pin:
        users = Users.query.all()
        random_pin = random.randint(1000, 9999)
        return render_template('admin.html',users=users,user_pin=user_pin,greeting=greeting,random_pin=random_pin)

    # . . . show managers page
    elif user_pin == manager_pin:
        return manager(selected_user)
    
    # . . . show user page
    else:
        
        # . . . show confirmed
        try:
            current_user = Users.query.filter_by(pin=user_pin).first()
            user_name = current_user.name
            if current_user.confirmed == 0:
                current_user.confirmed = 1
                db.session.commit()
                confirmed = 1
            else:
                confirmed = 0


            global clock_in_text
            global clock_out_text
            clock_in_text = 'Start Shift'
            clock_out_text = 'End Shift'

            # . . . load user history
            all_history = History.query.filter_by(name=user_name).order_by(History.start.desc()).all()
            most_recent_record = History.query.filter_by(name=user_name).order_by(History.start.desc()).first()

            # . . . find clock status by checking most recent record
            try:
                # . . . if record exits, check if start and end match
                if most_recent_record.end == most_recent_record.start:
                    clock_status = clock_out_text
                else:
                    clock_status =clock_in_text

            # . . . if no record exists, set to Start Shift
            except:
                clock_status = clock_in_text

            # . . display
            return render_template('user.html',user=user_name,history=all_history,clock_status=clock_status,user_pin=user_pin,greeting=greeting,clock_in_text=clock_in_text,clock_out_text=clock_out_text,confirmed=confirmed)
        
        except:
            return "Sorry, that pin is not associated with any user."
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - User Panel

# . . . Start Shift
@app.route("/clock_action",methods=['GET','POST'])
def clock_action():

    if request.method == 'POST':

        clock_status = request.form['clock_status']
        user_name = request.form['user']
        time_now = datetime.now()
        message_time_now =  time_now.strftime("%I:%M %p on %b %d, %Y")

        if clock_status == "Start Shift":
            new_record = History(name = user_name,start = time_now, end = time_now, report='')
            db.session.add(new_record)
            db.session.commit()

            # . . . Notify user
            email = (Users.query.filter_by(name = user_name).first()).email
            subject = "You've Clocked In"
            body = "You've clocked in at " + message_time_now + "."
            executor.submit(send_text,email,subject,body)

            # . . . Notify manager
            email = (Users.query.filter_by(type = 'manager').first()).email
            subject = user_name + " has clocked in."
            body = user_name + " has clocked in at " + message_time_now + "." 
            executor.submit(send_text,email,subject,body)
        
        elif clock_status == "End Shift":
            report = request.form['report']
            most_recent_record = History.query.filter_by(name=user_name).order_by(History.start.desc()).first()
            most_recent_record.end = time_now
            most_recent_record.report = report
            db.session.commit()

            # . . . send to user
            email = (Users.query.filter_by(name = user_name).first()).email
            subject = "You've Clocked Out"
            body = "You've clocked out at " + message_time_now + "."
            executor.submit(send_text,email,subject,body)

            # . . . send to manager
            email = (Users.query.filter_by(type = 'manager').first()).email
            subject = user_name + " has clocked out."
            body = user_name + " has clocked out at " + message_time_now + ". End of day report :" + report
            executor.submit(send_text,email,subject,body)

        # . . . find user pin and pass back to home 
        user_pin = (Users.query.filter(Users.name==user_name).first()).pin

        # . . . return using below method to ensure URL stays safe
        return redirect(url_for('home', user_pin=user_pin))

# take to update record screen
@app.route("/edit_record/<int:id>/<string:date>/<string:start_time>/<string:end_time>/<int:user_pin>/<string:selected_user>")
@app.route("/edit_record/<int:id>/<string:date>/<string:start_time>/<string:end_time>/<int:user_pin>")
def edit_record(id,date,start_time,end_time,user_pin,selected_user=None):
    return render_template('edit_record.html',id=id,date=date,start_time=start_time,end_time=end_time,user_pin=user_pin,selected_user=selected_user)
    
# commit update
@app.route("/commit_record",methods=['GET','POST'])
def commit_record():
    if request.method == 'POST':
        
        #. . . collect variables from form
        id = request.form['id']
        date = request.form['date']
        delete = request.form.get('delete','not_selected')
        user_pin = int(request.form['user_pin'])
        selected_user = request.form['selected_user']
        old_start_time = request.form['old_start_time']
        old_end_time = request.form['old_end_time']
        reason = request.form['reason']
        
        # . . . find manager information
        manager = Users.query.filter_by(type = 'manager').first()
        manager_name = manager.name
        manager_email = manager.email

        # . . . find user details
        if selected_user == 'None':

            # . . . if user change
            user = Users.query.filter_by(pin = user_pin).first()
            user_email = user.email
            current_user = user.name
    
        else:

            # . . . if manager change change
            user = Users.query.filter_by(name = selected_user).first()
            user_email = user.email
            current_user = user.name
        

        # . . .  Modify Record
        if delete == 'not_selected':
            new_start = request.form['new_start_time']
            new_end = request.form['new_end_time']

            # . . . convert string back into a date time object
            new_start_time = datetime.strptime(date + " " + new_start,'%b %d, %Y %H:%M')
            new_end_time = datetime.strptime(date + " " + new_end,'%b %d, %Y %H:%M')

            # . . . update record
            record_to_update = History.query.get_or_404(id)
            record_to_update.start = new_start_time
            record_to_update.end = new_end_time
            db.session.commit()

            #. . . set messages for notifications
            user_change_manager_subject = current_user + " has modified their working history."
            user_change_manager_body = current_user + " has modified their working history on " + date + " from " + old_start_time + " - " + old_end_time + " to " + new_start + " - " + new_end + " due to the following reason: " + reason + "."
            user_change_user_subject = "You have modified your working history."
            user_change_user_body = "You've modified your working history on " + date + " from " + old_start_time + " - " + old_end_time + " to " + new_start + " - " + new_end + " due to the following reason: " + reason + "."
            
            manager_change_manager_subject = "You have modified " + current_user + "'s working history."
            manager_change_manager_body = "You have modified " + current_user + "'s working history on " + date + " from " + old_start_time + " - " + old_end_time + " to " + new_start + " - " + new_end + " due to the following reason: " + reason + "."
            manager_change_user_subject = manager_name + " has modified your working history."
            manager_change_user_body = manager_name + " has modified your working history on " + date + " from " + old_start_time + " - " + old_end_time + " to " + new_start + " - " + new_end + " due to the following reason: " + reason + "."
        

        # . . . Delete Record
        else:
            # . . . delete record
            record_to_delete = History.query.get_or_404(id)
            db.session.delete(record_to_delete)
            db.session.commit()

            # . . . set messages for notifications
            user_change_manager_subject = current_user + " has deleted their working history."
            user_change_manager_body = current_user + " has deleted their working history on " + date + " from " + old_start_time + " - " + old_end_time + " due to the following reason: " + reason + "."
            user_change_user_subject = "You've deleted your working history."
            user_change_user_body = "You've deleted deleted your working history on " + date + " from " + old_start_time + " - " + old_end_time + " due to the following reason: " + reason + "."
            
            manager_change_manager_subject = "You've deleted " + current_user + "'s work history record"
            manager_change_manager_body = "You've deleted " + current_user + "'s work history record on " + date + " from " + old_start_time + " - " + old_end_time + " due to the following reason: " + reason + "."
            manager_change_user_subject = manager_name + " has deleted your working history."
            manager_change_user_body = manager_name + " has deleted your working history on " + date + " from " + old_start_time + " - " + old_end_time + " due to the following reason: " + reason + "."
       
        # . . . send notification
        if selected_user == 'None':

            # . . . if this is a user change
            user = Users.query.filter_by(pin = user_pin).first()
            user_email = user.email
            current_user = user.name

            # . . . send message to manager and user
            executor.submit(send_text,manager_email,user_change_manager_subject,user_change_manager_body)
            executor.submit(send_text,user_email,user_change_user_subject,user_change_user_body)
            
        else:
            
            # . . . if this is a manager change
            user = Users.query.filter_by(name = selected_user).first()
            user_email = user.email
            current_user = user.name

            executor.submit(send_text,manager_email,manager_change_manager_subject,manager_change_manager_body)
            executor.submit(send_text,user_email,manager_change_user_subject,manager_change_user_body)

        if selected_user == 'None':
            return redirect(url_for('home', user_pin=user_pin,selected_user=selected_user))
        else:
            return home(user_pin=user_pin,selected_user=selected_user)

    else:
        pass

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - Admin's Panel

# create user
@app.route("/create_user",methods=['GET','POST'])
def create_user():
    if request.method == 'POST':

        try:
            # . . . collect variables from form
            name = request.form['user']
            email = request.form['email']
            pin = request.form['pin']
            type = request.form['user_type']

            # . . . create new user
            new_user = Users(name=name,email=email,pin=pin,type=type,confirmed=0)

            # . . . add and commit
            db.session.add(new_user)
            db.session.commit()

            
            subject = "Your KIG Payroll Account has been created"
            url = url_for('home', user_pin=pin)
            body = "Please confirm your account by clicking this link below: \n" + url +"\n . . . . "
            print("email: " + email + " subject: " + subject + " body: " + body)
            
            executor.submit(send_text,email,subject,body)
            
            # . . . refresh
            return home(admin_pin)
        except:
            return "error"
    
# delete user
@app.route("/delete_user/<int:user_id>")
def delete_user(user_id):

    # . . . find user in db
    user_to_delete = Users.query.get_or_404(user_id)
    name_to_delete = user_to_delete.name
    print(name_to_delete + " is ready to be deleted.")

    #. . . history to delete
    history_to_delete = History.query.filter_by(name=name_to_delete).all()
    try:
        for record in history_to_delete:
            history_to_delete_id = History.query.get_or_404(record.id)
            db.session.delete(history_to_delete_id)

            print("delete completed.")
        
        db.session.commit()
    except:
        for record in history_to_delete:
            print("error deleting history" + record.name)
    
    # . . . delete user and commit
    db.session.delete(user_to_delete)
    db.session.commit()

    # . . . refresh
    return redirect(url_for('home', user_pin=admin_pin))

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - Manager's Panel

# show managers's page
@app.route("/manager/<int:user_pin>/<string:selected_user>")
def manager(selected_user=None):

    print(selected_user)
    
    users = Users.query.filter_by(type = 'crew_member').all()
    user_history = History.query.filter_by(name=selected_user).order_by(History.start.desc()).all()
    manager_pin = (Users.query.filter_by(type = 'manager').first()).pin
    
    return render_template('manager.html',users=users,history=user_history,user_pin=manager_pin,selected_user=selected_user,greeting=greeting)

# select user
@app.route("/manager_select_user",methods=['GET','POST'])
def manager_select_user():
    if request.method == 'POST':
        selected_user = request.form['selected_user']
        return manager(selected_user)
    else:
        pass

# export csv
@app.route("/export_csv_action")
def export_csv_action():
    # replace 'YourTable' with the name of your table
    data = History.query.all()

    # write the data to a CSV file in memory
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Crew Member', 'Date' ,'Start Time', 'End Time','Daily Report'])
    for row in data:
        writer.writerow([row.name, row.start.strftime("%b %d, %Y"), row.start.strftime("%I:%M %p"), row.end.strftime("%I:%M %p"), row.report])  # replace with your column names

    # create a response object and set its headers
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=all_history.csv'
    response.headers['Content-type'] = 'text/csv'

    return response

# : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : Functions

# send texts
def send_text(email,subject,body):

    print("email command initiated" + email + subject + body)

    email_to = email
    email_from = 'benjaminlawson4@gmail.com'

    # Email message
    message = MIMEMultipart()
    message['From'] = 'benjaminlawson4@gmail.com'
    message['To'] = email
    message['Subject'] = subject
    message.attach(MIMEText(body, 'plain'))

    # SMTP server and login credentials
    smtp_server = 'smtp.gmail.com'
    smtp_port = 587
    smtp_username = 'benjaminlawson4@gmail.com'
    smtp_password = 'qwkgpigpnwtxeutt'

    # Send email
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        text = message.as_string()
        server.sendmail(email_from, email_to, text)
        print("email sent")

# : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : Run App

with app.app_context():
    db.create_all()
app.run(debug=True, host="0.0.0.0", port=5000)
