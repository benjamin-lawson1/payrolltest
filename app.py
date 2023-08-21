# : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : Set Up Application

from flask import Flask, render_template, request, redirect, url_for, make_response
import twilio
from twilio.rest import Client
import sched
import math
import time
import datetime as dt
from datetime import datetime, timedelta
import random
from flask_migrate import Migrate
from sqlalchemy import create_engine


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
import os

# . . . allows app to run 1 thread in the background
executor = ThreadPoolExecutor(2)

# . . . identify the application
app = Flask(__name__)

# : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : Create Databases

# . . . set up SQL database
global notifications

# . . . use this setting to turn off email notifications for testing
notifications = True
database_url = os.environ.get('DATABASE_URL', 'sqlite:///test.db').replace("postgres://", "postgresql://")
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
db = SQLAlchemy(app)
migrate = Migrate(app, db)

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
    did_drive = db.Column(db.Boolean)

# . . . add db: Users (id, name, email, pin)
class PastActions(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.DateTime)
    action = db.Column(db.String(500), nullable=False)

# : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : Create Routes


work_week_start = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - dt.timedelta(days=dt.datetime.now().weekday())
work_week_end = work_week_start + dt.timedelta(days=6)
today = datetime.today()

@app.route("/")
def website_load():
    return 'no pin entered.'

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - Home Screen
@app.route("/<int:user_pin>")
def home(user_pin,selected_user=None):
    
    # . . . if db is empty, create default users
    if Users.query.first() == None:
        
        # . . . create list, append users, add to db
        new_users = []
        
        new_users.append(Users(name='Benjamin',email='Benjamin@KiawahIslandGetaways.com',pin='8475',type='admin',confirmed=1))
        new_users.append(Users(name='Shawn',email='8433437215@tmomail.net',pin='6817',type='manager',confirmed=1))
        
        for user in new_users:
            db.session.add(user)
        
        db.session.commit()

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ Collect Data

    # . . determine the manager pin, admin pin
    global manager_pin
    global admin_pin
    manager_pin = (Users.query.filter_by(type = 'manager').first()).pin
    admin_pin = (Users.query.filter_by(type = 'admin').first()).pin
    
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
        history = PastActions.query.order_by(PastActions.time.desc()).filter(PastActions.time >= work_week_start)
        random_pin = random.randint(1000, 9999)

        return render_template('admin.html',users=users,user_pin=user_pin,greeting=greeting,random_pin=random_pin,history=history)

    # . . . show managers page
    elif user_pin == manager_pin:

        add_to_record("The manager's page has been viewed.")

        return manager(selected_user)
    
    # . . . show user page
    else:
        
        # . . . show confirmed
        try:
            current_user = Users.query.filter_by(pin=user_pin).first()
            user_name = current_user.name

            if "Jessica" in user_name or "Chrystal" in user_name:
                show_drive_checkbox = True
            else:
                show_drive_checkbox = False
                
            if current_user.confirmed == 0:
                current_user.confirmed = 1
                db.session.commit()
                confirmed = 1

                add_to_record(user_name + "'s account has been confirmed.")

                #. . . Alert Admin
                executor.submit(send_text_message('8433430072', user_name + ' has confirmed their account.'))
            
            else:
                confirmed = 0


            global clock_in_text
            global clock_out_text
            clock_in_text = 'Start Shift'
            clock_out_text = 'End Shift'

            # . . . load user history
            all_history = History.query.filter_by(name=user_name).order_by(History.start.desc()).filter(History.start >= work_week_start)
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

            #. . . Add to records
            action = user_name + " account viewed."
            db.session.add(PastActions(time = datetime.now(),action = action))
            db.session.commit()

            # . . display
            return render_template('user.html',user=user_name,history=all_history,clock_status=clock_status,user_pin=user_pin,greeting=greeting,clock_in_text=clock_in_text,clock_out_text=clock_out_text,confirmed=confirmed,show_drive_checkbox=show_drive_checkbox)
        
        except:
            return "Sorry, that pin is not associated with any user."
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - User Panel

# . . . Start Shift
@app.route("/clock_action",methods=['GET','POST'])
def clock_action():

    if request.method == 'POST':
        shawn_email = '18433435075'
        jeanette_email = '18433437215'
        clock_status = request.form['clock_status']
        user_name = request.form['user']
        user_email = (Users.query.filter_by(name = user_name).first()).email
        time_now = datetime.now()
        message_time_now =  time_now.strftime("%I:%M %p on %b %d, %Y")

        if clock_status == "Start Shift":

            # Get Drive Status
            try:
                did_drive = request.form['did_drive']
                if did_drive == "True":
                    did_drive = True
                    print("User drove to work.")
            except:
                if "Jessica" in user_name or "Chrystal" in user_name:
                    did_drive = False
                else:
                    did_drive = None

            new_record = History(name = user_name,start = time_now, end = time_now, report='',did_drive = did_drive)
            db.session.add(new_record)
            db.session.commit()
             
            add_to_record(user_name + " has clocked in.")

            # . . . Notify user
            subject = "You've Clocked In"
            body = "You've clocked in at " + message_time_now + "."
            executor.submit(send_text_message, user_email, body)

            # . . . Notify manager
            subject = user_name + " has clocked in."
            body = user_name + " has clocked in at " + message_time_now + "." 
            executor.submit(send_text_message, shawn_email,body)
            executor.submit(send_text_message, jeanette_email,body)
        
        elif clock_status == "End Shift":
            report = request.form['report']
            most_recent_record = History.query.filter_by(name=user_name).order_by(History.start.desc()).first()
            most_recent_record.end = time_now
            most_recent_record.report = report
            db.session.commit()

            add_to_record(user_name + " has clocked out.")

            # . . . send to user
            subject = "You've Clocked Out"
            body = "You've clocked out at " + message_time_now + "."
            executor.submit(send_text_message,user_email,body)

            # . . . send to manager
            subject = user_name + " has clocked out."
            body = user_name + " has clocked out at " + message_time_now + ". End of day report :" + report
            executor.submit(send_text_message,shawn_email,body)
            executor.submit(send_text_message,jeanette_email,body)

        # . . . find user pin and pass back to home 
        user_pin = (Users.query.filter(Users.name==user_name).first()).pin

        # . . . return using below method to ensure URL stays safe
        return redirect(url_for('home', user_pin=user_pin))

# take to update record screen
@app.route("/edit_record/<int:id>/<string:date>/<string:start_time>/<string:end_time>/<int:user_pin>/<string:did_drive>/<string:selected_user>")
@app.route("/edit_record/<int:id>/<string:date>/<string:start_time>/<string:end_time>/<string:did_drive>/<int:user_pin>")
def edit_record(id,date,start_time,end_time,user_pin,did_drive,selected_user=None):
    date_object = datetime.strptime(date, '%b %d, %Y')
    return render_template('edit_record.html',id=id,date=date_object,start_time=start_time,end_time=end_time,user_pin=user_pin,did_drive=did_drive,selected_user=selected_user)
    
# commit update
@app.route("/commit_record",methods=['GET','POST'])
def commit_record():
    if request.method == 'POST':
        
        #. . . collect variables from form
        id = request.form['id']
        post_date = request.form['date']
        post_new_date = request.form['new_date']
        date = datetime.strptime(request.form['new_date'], '%Y-%m-%d')
        delete = request.form.get('delete','not_selected')
        user_pin = int(request.form['user_pin'])
        selected_user = request.form['selected_user']
        old_start_time = request.form['old_start_time']
        old_end_time = request.form['old_end_time']
        reason = request.form['reason']
        new_start = request.form['new_start_time']
        new_end = request.form['new_end_time']
        new_start_time = datetime.strptime(date.strftime("%b %d, %Y") + " " + new_start,'%b %d, %Y %H:%M')
        new_end_time = datetime.strptime(date.strftime("%b %d, %Y") + " " + new_end,'%b %d, %Y %H:%M')
        
        selected_user = Users.query.filter_by(pin = user_pin).first()
        selected_user = selected_user.name
        if "Jessica" in selected_user or "Chrystal" in selected_user:
            try:
                did_drive = request.form['did_drive'] 
                if did_drive == "True":
                    did_drive = True
            except:
                did_drive = False
        else:
            did_drive = None

        if new_end_time < new_start_time:
            return('Error: Your end time is before your start time! Please press "Back" to edit.')
        
        else:

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
                new_start_time = datetime.strptime(date.strftime("%b %d, %Y") + " " + new_start,'%b %d, %Y %H:%M')
                new_end_time = datetime.strptime(date.strftime("%b %d, %Y") + " " + new_end,'%b %d, %Y %H:%M')

                # . . . update record
                record_to_update = History.query.get_or_404(id)
                record_to_update.start = new_start_time
                record_to_update.end = new_end_time
                record_to_update.did_drive = did_drive
                db.session.commit()
                
                reason_string = post_date + " (" + old_start_time + " - " + old_end_time + ") to " + post_new_date + "(" + new_start + " - " + new_end + ") due to the following reason: " + reason + "."
                add_to_record(current_user + " has modified their working history from " + reason_string)

                #. . . set messages for notifications
                user_change_manager_subject = current_user + " has modified their working history."
                user_change_manager_body = current_user + " has modified their working history on " + reason_string
                user_change_user_subject = "You have modified your working history."
                user_change_user_body = "You've modified your working history on " + reason_string
                
                manager_change_manager_subject = "You have modified " + current_user + "'s working history."
                manager_change_manager_body = "You have modified " + current_user + "'s working history on " + reason_string
                manager_change_user_subject = manager_name + " has modified your working history."
                manager_change_user_body = manager_name + " has modified your working history on " + reason_string
            

            # . . . Delete Record
            else:
                # . . . delete record
                record_to_delete = History.query.get_or_404(id)
                db.session.delete(record_to_delete)
                db.session.commit()

                add_to_record(current_user + " has deleted their working history on " + str(date) + " from " + old_start_time + " - " + old_end_time + " due to the following reason: " + reason + ".")

                # . . . set messages for notifications
                user_change_manager_subject = current_user + " has deleted their working history."
                user_change_manager_body = current_user + " has deleted their working history on " + str(date) + " from " + old_start_time + " - " + old_end_time + " due to the following reason: " + reason + "."
                user_change_user_subject = "You've deleted your working history."
                user_change_user_body = "You've deleted deleted your working history on " + str(date) + " from " + old_start_time + " - " + old_end_time + " due to the following reason: " + reason + "."
                
                manager_change_manager_subject = "You've deleted " + current_user + "'s work history record"
                manager_change_manager_body = "You've deleted " + current_user + "'s work history record on " + str(date) + " from " + old_start_time + " - " + old_end_time + " due to the following reason: " + reason + "."
                manager_change_user_subject = manager_name + " has deleted your working history."
                manager_change_user_body = manager_name + " has deleted your working history on " + str(date) + " from " + old_start_time + " - " + old_end_time + " due to the following reason: " + reason + "."
        
            # . . . send notification
            if selected_user == 'None':

                # . . . if this is a user change
                user = Users.query.filter_by(pin = user_pin).first()
                user_email = user.email
                current_user = user.name

                # . . . send message to manager and user
                executor.submit(send_text_message,manager_email,user_change_manager_subject,user_change_manager_body)
                executor.submit(send_text_message,user_email,user_change_user_subject,user_change_user_body)
                
            else:
                
                # . . . if this is a manager change
                user = Users.query.filter_by(name = selected_user).first()
                user_email = user.email
                current_user = user.name

                executor.submit(send_text_message,manager_email,manager_change_manager_subject,manager_change_manager_body)
                executor.submit(send_text_message,user_email,manager_change_user_subject,manager_change_user_body)

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

            
            subject = "Your KIG Payroll Account has been created!"
            url = "https://kigpayroll.herokuapp.com/" + pin
            body = "You may access your account by clicking on the link below: \n" + url + "\n \n Please start using this app to clock in starting Monday, March 13th. Thank you, Benjamin. "
            print("email: " + email + " subject: " + subject + " body: " + body)

            add_to_record("A new account has been created for " + name + ".")
            
            executor.submit(send_text_message,email,body)
            
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

    add_to_record(name_to_delete + " 's account has been deleted.")

    # . . . refresh
    return redirect(url_for('home', user_pin=admin_pin))

# edit user
@app.route("/edit_user/<string:user_name>/<string:user_email>",methods=['GET','POST'])
@app.route("/edit_user",methods=['GET','POST'])
def edit_user(user_name=None,user_email=None):

    if request.method == 'POST':
        old_name = request.form['old_name']
        new_name = request.form['new_name']
        new_email = request.form['new_email']

        update_user = Users.query.filter_by(name=old_name).first()
        update_user.name = new_name
        update_user.email = new_email
        db.session.commit()

        update_history = History.query.filter_by(name=old_name).all()
        for record in update_history:
            record_to_update = History.query.get_or_404(record.id)
            record_to_update.name = new_name
            db.session.commit()

        add_to_record(old_name + "'s account has been updated to " + new_name + " (" + new_email + ")")

        return home(user_pin=admin_pin)
    
    # . . . refresh
    return render_template('edit_user.html', user_name=user_name,user_email=user_email)

# submit report
@app.route("/weekly_report_form",methods=['GET','POST'])
def weekly_report_form():

    if request.method == 'POST':
        try:
            report_start_date = datetime.strptime(request.form['report_start_date'], '%Y-%m-%d')
            report_end_date = datetime.strptime(request.form['report_end_date'], '%Y-%m-%d')
            function = request.form['function']
            
            preview = send_weekly_report(report_start_date,report_end_date,function)
            
            if function == "live":
                return "report sent!"
            else:
                return render_template('submit_report.html', report_start_date = request.form['report_start_date'], report_end_date = request.form['report_end_date'],preview=preview)
        except:
            return "error"

    # . . . load form
    report_start_date = work_week_start.strftime('%Y-%m-%d')
    report_end_date = work_week_end.strftime('%Y-%m-%d')
    return render_template('submit_report.html', report_start_date = report_start_date, report_end_date = report_end_date)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - Manager's Panel

# show managers's page
@app.route("/manager/<int:user_pin>/<string:selected_user>")
def manager(selected_user=None):

    print(selected_user)
    
    users = Users.query.filter_by(type = 'crew_member').all()

    if today.weekday() == 0:
        user_history = History.query.filter_by(name=selected_user).order_by(History.start.desc()).filter(History.start >= work_week_start - dt.timedelta(days=7))
    else:
        user_history = History.query.filter_by(name=selected_user).order_by(History.start.desc()).filter(History.start >= work_week_start)

    manager_pin = (Users.query.filter_by(type = 'manager').first()).pin
    
    return render_template('manager.html',users=users,history=user_history,user_pin=manager_pin,selected_user=selected_user,greeting=greeting)

# select user
@app.route("/manager_select_user",methods=['GET','POST'])
def manager_select_user():
    if request.method == 'POST':
        selected_user = request.form['selected_user']

        add_to_record("The manager has viewed " + selected_user + "'s work history.")

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

    add_to_record("Work history has been exported.")

    return response

# : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : Functions
"""
def schedule_automated_weekly_report():
    s = sched.scheduler(time.time, time.sleep)
    next_run_time = datetime.now().replace(hour=23, minute=0, second=0, microsecond=0)
    if next_run_time.weekday() != 6:  # Sunday is weekday number 6
        days_to_sunday = (6 - next_run_time.weekday()) % 7
        next_run_time += timedelta(days=days_to_sunday)
    s.enterabs(next_run_time.timestamp(), 1, send_weekly_report, ())
    s.run()
"""

def send_weekly_report(start_report_date,end_report_date,function):

    # ... find users
    crew_members = Users.query.order_by(Users.id.asc()).all()
    crew_members = [crew_member for crew_member in crew_members if crew_member.name != "Ben - Work"]
    crew_member_weekly_summary_list = ''
    website_output = ''

    # . . . for each user
    for crew_member in crew_members:
        print(crew_member.name)
        crew_member_name = crew_member.name
        crew_member_records = ''
        crew_member_weekly_hour_total = 0
        days = []

        #  . . . find user records
        crew_member_working_records = History.query.filter_by(name=crew_member_name).filter(History.start >= start_report_date,History.end <= end_report_date).all()

        for record in crew_member_working_records:
            try: 
                # . . . collect data
                day = str(record.start.strftime('%a'))
                record_start_time = str(record.start.strftime('%I:%M %p'))
                record_end_time = str(record.end.strftime('%I:%M %p'))
                record_time_total = round((record.end - record.start).total_seconds() / 3600,1)
                record_time_total_string = str(record_time_total)
                days_drove_to_work = record.did_drive
                
                if days_drove_to_work == True:
                    days.append(day)
            
                
                # . . . compile message: Mon: 9:30AM - 10:30AM | 1 hour(s)
                compiled_record = day + ': ' + record_start_time + " - " + record_end_time + " | " + record_time_total_string + " hour(s) <br>"

                # . . . add message to records
                crew_member_records += compiled_record
                crew_member_weekly_hour_total += record_time_total

                # . . . add day to days
                

            except:
                print('error')
        
        start_of_working_week = str(start_report_date.strftime('%m/%d/%Y'))
        end_of_working_week = str(end_report_date.strftime('%m/%d/%Y'))
        crew_member_weekly_hour_total_string = str(math.ceil(crew_member_weekly_hour_total*4)/4)
        crew_member_email = (Users.query.filter_by(name=crew_member_name).first()).email
        drive_days = str(len(set(days)))

        # . . . compile message: Hi Jessica, here are your working hours for this week(1/1/2023 - 1/7/2023): ... in total, you worked 14 hours this week.
        crew_member_compiled_message = 'Hi ' + crew_member_name + ', here is your working report for this week(' + start_of_working_week + " - " + end_of_working_week + '): <br><br>' + crew_member_records + '<br> In total, you worked a total of ' + crew_member_weekly_hour_total_string + ' hour(s) this week and drove in ' + drive_days + ' day(s) this week.<br> <br> <br>'
        

        # . . . compile crew member weekly summary for manager report: Jessica - 15 hours
        crew_member_weekly_summary_record = crew_member_name + ' - ' + crew_member_weekly_hour_total_string + ' hour(s) | ' + str(drive_days) + ' drive day(s) <br>' 
        

        
        if crew_member_weekly_hour_total > 0:
            website_output += crew_member_compiled_message
            if function == "live":
                send_text(crew_member_email,"Your Weekly Working Report",crew_member_compiled_message)
            crew_member_weekly_summary_list += crew_member_weekly_summary_record
        else:
            pass
        
    # . . . email manager here
    manager_email = 'shawn@kiawahislandgetaways.com'
    manager_report_body = 'Hi Shawn, here is your payroll report:<br><br>' + crew_member_weekly_summary_list + '<br> Have a great day!'
    manager_report_header = 'Crew Working Hours for week of ' + start_of_working_week + ' - ' + end_of_working_week
    if function == "live":
        send_text(manager_email,manager_report_header,manager_report_body)
    
    website_output += manager_report_body
    if function == "live":
        send_text("benjamin@kiawahislandgetaways.com","Weekly report has been sent",website_output)

    return website_output

# add to records
def add_to_record(action):
    db.session.add(PastActions(time = datetime.now(),action = action))
    db.session.commit()

# send texts
def send_text(email,subject, body):

    email_from = 'benjaminlawson4@Gmail.com'
    password = 'akaiktlmkjggqmlj'

    print("email command initiated" + email + subject + body)

    email_to = email
    email_from = email_from

    # Email message
    message = MIMEMultipart()
    message['From'] = email_from
    message['To'] = email
    message['Subject'] = subject
    message.attach(MIMEText(body, 'html'))

    # SMTP server and login credentials
    smtp_server = 'smtp.gmail.com'
    smtp_port = 587
    smtp_username = email_from
    smtp_password = password

    # Send email
    if notifications == True:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            text = message.as_string()
            server.sendmail(email_from, email_to, text)
            print("email sent")
    else:
        pass

def send_text_message(phone_number, body):
    # Twilio credentials
    account_sid = 'AC3a05bf7e7d0967566a90868881946b6e'
    auth_token = '76e2bca4375345370a84d4f22d9a327c'

    client = Client(account_sid, auth_token)

    message = client.messages.create(
        body=body,
        from_='+18039415612',
        to=phone_number
    )

    print("Text message sent")

# : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : Run App

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
    # schedule_automated_weekly_report()
