# : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : Set Up Application

# . . . import Flask
from flask import Flask, render_template, request, redirect, url_for, make_response
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

# . . . add db: Users (id, name, email, pin)
class PastActions(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.DateTime)
    action = db.Column(db.String(500), nullable=False)

# : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : : Create Routes

# create global variables
global start_date, end_date

start_date = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - dt.timedelta(days=dt.datetime.now().weekday())
end_date = start_date + dt.timedelta(days=6)

@app.route("/")
def website_load():

    # ... find users
    crew_members = Users.query.all()
    website_output = ''
    crew_member_weekly_summary_list = ''

    # . . . for each user
    for crew_member in crew_members:
        crew_member_name = crew_member.name
        crew_member_records = ''
        crew_member_weekly_hour_total = 0
        days = []

        #  . . . find user records
        crew_member_working_records = History.query.filter_by(name=crew_member_name).filter(History.start > start_date).all()

        for record in crew_member_working_records:
            try: 
                # . . . collect data
                day = str(record.start.strftime('%a'))
                record_start_time = str(record.start.strftime('%I:%M %p'))
                record_end_time = str(record.end.strftime('%I:%M %p'))
                record_time_total = round((record.end - record.start).total_seconds() / 3600,1)
                record_time_total_string = str(record_time_total)
                
                # . . . compile message: Mon: 9:30AM - 10:30AM | 1 hour(s)
                compiled_record = day + ': ' + record_start_time + " - " + record_end_time + " | " + record_time_total_string + " hour(s) <br>"

                # . . . add message to records
                crew_member_records += compiled_record
                crew_member_weekly_hour_total += record_time_total

                # . . . add day to days
                days.append(day)

            except:
                print('error')
        
        start_of_working_week = str(start_date.strftime('%m/%d/%Y'))
        end_of_working_week = str(end_date.strftime('%m/%d/%Y'))
        crew_member_weekly_hour_total_string = str(crew_member_weekly_hour_total)
        crew_member_email = (Users.query.filter_by(name=crew_member_name).first()).email
        crew_member_number_working_days = len(set(days))

        # . . . compile message: Hi Jessica, here are your working hours for this week(1/1/2023 - 1/7/2023): ... in total, you worked 14 hours this week.
        crew_member_compiled_message = 'Hi ' + crew_member_name + ', here are your working hours for this week(' + start_of_working_week + " - " + end_of_working_week + '): <br><br>' + crew_member_records + '<br> In total, you worked ' + str(crew_member_number_working_days) + ' days, for a total of ' + crew_member_weekly_hour_total_string + ' hours this week. <br> <br> This will be send to '+ crew_member_email + ' on ' + str(end_date) + '<br> - - - <br>'
        

        # . . . compile crew member weekly summary for manager report: Jessica - 15 hours
        crew_member_weekly_summary_record = crew_member_name + ' - ' + str(crew_member_weekly_hour_total) + 'hour(s) | ' + str(crew_member_number_working_days) + ' working day(s)' 
        crew_member_weekly_summary_list += crew_member_weekly_summary_record

        
        if crew_member_weekly_hour_total > 0:
            # . . . email crew member here
            website_output += crew_member_compiled_message
        else:
            pass
        
    
    manager_report = 'Hi Shawn, here is your payroll report:<br>' + crew_member_weekly_summary_list + '<br> Have a great day!'
    website_output += manager_report

    return website_output


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
            if current_user.confirmed == 0:
                current_user.confirmed = 1
                db.session.commit()
                confirmed = 1

                add_to_record(user_name + "'s account has been confirmed.")

                #. . . Alert Admin
                executor.submit(send_text,'8433430072@tmomail.net','Account Confirmed',user_name + ' has confirmed their account.')
            
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
            return render_template('user.html',user=user_name,history=all_history,clock_status=clock_status,user_pin=user_pin,greeting=greeting,clock_in_text=clock_in_text,clock_out_text=clock_out_text,confirmed=confirmed)
        
        except:
            return "Sorry, that pin is not associated with any user."
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - User Panel

# . . . Start Shift
@app.route("/clock_action",methods=['GET','POST'])
def clock_action():

    if request.method == 'POST':
        shawn_email = '8433435075@tmomail.net'
        jeanette_email = '8433437215@tmomail.net'
        clock_status = request.form['clock_status']
        user_name = request.form['user']
        user_email = (Users.query.filter_by(name = user_name).first()).email
        time_now = datetime.now()
        message_time_now =  time_now.strftime("%I:%M %p on %b %d, %Y")

        if clock_status == "Start Shift":
            new_record = History(name = user_name,start = time_now, end = time_now, report='')
            db.session.add(new_record)
            db.session.commit()
             
            add_to_record(user_name + " has clocked in.")

            # . . . Notify user
            subject = "You've Clocked In"
            body = "You've clocked in at " + message_time_now + "."
            executor.submit(send_text,user_email,subject,body)

            # . . . Notify manager
            subject = user_name + " has clocked in."
            body = user_name + " has clocked in at " + message_time_now + "." 
            executor.submit(send_text,shawn_email,subject,body)
            executor.submit(send_text,jeanette_email,subject,body)
        
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
            executor.submit(send_text,user_email,subject,body)

            # . . . send to manager
            subject = user_name + " has clocked out."
            body = user_name + " has clocked out at " + message_time_now + ". End of day report :" + report
            executor.submit(send_text,shawn_email,subject,body)
            executor.submit(send_text,jeanette_email,subject,body)

        # . . . find user pin and pass back to home 
        user_pin = (Users.query.filter(Users.name==user_name).first()).pin

        # . . . return using below method to ensure URL stays safe
        return redirect(url_for('home', user_pin=user_pin))

# take to update record screen
@app.route("/edit_record/<int:id>/<string:date>/<string:start_time>/<string:end_time>/<int:user_pin>/<string:selected_user>")
@app.route("/edit_record/<int:id>/<string:date>/<string:start_time>/<string:end_time>/<int:user_pin>")
def edit_record(id,date,start_time,end_time,user_pin,selected_user=None):
    date_object = datetime.strptime(date, '%b %d, %Y')
    return render_template('edit_record.html',id=id,date=date_object,start_time=start_time,end_time=end_time,user_pin=user_pin,selected_user=selected_user)
    
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

            add_to_record(current_user + " has deleted their working history on " + date + " from " + old_start_time + " - " + old_end_time + " due to the following reason: " + reason + ".")

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

            
            subject = "Your KIG Payroll Account has been created!"
            url = "https://kigpayroll.herokuapp.com/" + pin
            body = "You may access your account by clicking on the link below: \n" + url + "\n \n Please start using this app to clock in starting Monday, March 13th. Thank you, Benjamin. "
            print("email: " + email + " subject: " + subject + " body: " + body)

            add_to_record("A new account has been created for " + name + ".")
            
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

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - Manager's Panel

# show managers's page
@app.route("/manager/<int:user_pin>/<string:selected_user>")
def manager(selected_user=None):

    print(selected_user)
    
    users = Users.query.filter_by(type = 'crew_member').all()
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

# add to records
def add_to_record(action):
    db.session.add(PastActions(time = datetime.now(),action = action))
    db.session.commit()

# send texts
def send_text(email,subject,body):

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
    message.attach(MIMEText(body, 'plain'))

    # SMTP server and login credentials
    smtp_server = 'smtp.gmail.com'
    smtp_port = 587
    smtp_username = email_from
    smtp_password = password

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

if __name__ == '__main__':
    app.run(debug=True)
