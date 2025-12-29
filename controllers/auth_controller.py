"""
认证控制器
处理用户认证相关的路由
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, logout_user

from services import AuthService

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember_me = request.form.get('remember_me', False)
        
        success, message, user = AuthService.login(username, password, remember_me)
        
        if success:
            flash(message, 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
        else:
            flash(message, 'error')
    
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    """退出登录"""
    success, message = AuthService.logout()
    flash(message, 'info' if success else 'error')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册（如果需要开放注册）"""
    # 这里可以实现用户注册功能
    # 目前系统主要通过管理员创建用户
    flash('用户注册功能暂未开放，请联系管理员', 'info')
    return redirect(url_for('auth.login'))