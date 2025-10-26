from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse  # Änderung hier: wir nutzen urllib statt werkzeug
from models import User, db

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user is None or not user.check_password(request.form['password']):
            flash('Ungültiger Benutzername oder Passwort')
            return redirect(url_for('auth.login'))
        
        login_user(user)
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':  # Änderung hier
            next_page = url_for('home')
        return redirect(next_page)
    
    return render_template('auth/login.html')

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user is not None:
            flash('Bitte wählen Sie einen anderen Benutzernamen.')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(email=request.form['email']).first() is not None:
            flash('Bitte verwenden Sie eine andere E-Mail-Adresse.')
            return redirect(url_for('auth.register'))
        
        user = User(
            username=request.form['username'],
            email=request.form['email'],
            work_percentage=int(request.form['work_percentage'])
        )
        user.set_password(request.form['password'])
        db.session.add(user)
        db.session.commit()
        
        flash('Registrierung erfolgreich!')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))