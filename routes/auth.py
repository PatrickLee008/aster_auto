"""
用户认证路由
"""

from flask import Blueprint, request, render_template, redirect, url_for, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from models import User
from models.base import db

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            if request.is_json:
                return jsonify({'success': False, 'message': '用户名和密码不能为空'})
            flash('用户名和密码不能为空', 'error')
            return render_template('auth/login.html')
        
        # 查找用户
        print(f"[DEBUG LOGIN] 尝试登录用户: {username}")
        
        # 查找用户（允许禁用用户登录）
        user = User.query.filter_by(username=username).first()
        
        print(f"[DEBUG LOGIN] 找到用户: {user is not None}")
        
        if user:
            print(f"[DEBUG LOGIN] 用户ID: {user.id}, 昵称: {user.nickname}")
            print(f"[DEBUG LOGIN] 用户状态: is_active={user.is_active}")
            print(f"[DEBUG LOGIN] 密码哈希: {user.password_hash[:50]}...")
            password_match = user.check_password(password)
            print(f"[DEBUG LOGIN] 密码匹配: {password_match}")
        
        if user and user.check_password(password):
            # 登录成功
            login_user(user)
            user.update_last_login()
            
            if request.is_json:
                return jsonify({'success': True, 'message': '登录成功'})
            
            # 重定向到原来要访问的页面
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
        else:
            # 提供更详细的错误信息
            error_message = '用户名或密码错误'
            
            if not user:
                error_message = '用户名或密码错误'
            elif user:
                error_message = '密码错误'
            
            if request.is_json:
                return jsonify({'success': False, 'message': error_message})
            flash(error_message, 'error')
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """用户登出"""
    logout_user()
    flash('已成功登出', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册（仅管理员可访问）"""
    # 检查是否已有用户，如果没有用户，允许注册第一个管理员
    user_count = User.query.count()
    if user_count > 0 and (not current_user.is_authenticated or not current_user.is_admin):
        flash('只有管理员可以注册新用户', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        username = data.get('username')
        password = data.get('password')
        nickname = data.get('nickname')
        email = data.get('email', '')
        max_tasks = int(data.get('max_tasks', 5))
        is_admin = bool(data.get('is_admin', False))
        
        # 验证数据
        if not username or not password or not nickname:
            message = '用户名、密码和昵称不能为空'
            if request.is_json:
                return jsonify({'success': False, 'message': message})
            flash(message, 'error')
            return render_template('auth/register.html')
        
        # 检查用户名是否已存在
        if User.query.filter_by(username=username).first():
            message = '用户名已存在'
            if request.is_json:
                return jsonify({'success': False, 'message': message})
            flash(message, 'error')
            return render_template('auth/register.html')
        
        # 创建新用户
        try:
            user = User(
                username=username,
                nickname=nickname,
                email=email if email else None,
                max_tasks=max_tasks,
                is_admin=is_admin if user_count == 0 else False  # 第一个用户自动成为管理员
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            message = f'用户 {username} 注册成功'
            if request.is_json:
                return jsonify({'success': True, 'message': message})
            flash(message, 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            db.session.rollback()
            message = f'注册失败：{str(e)}'
            if request.is_json:
                return jsonify({'success': False, 'message': message})
            flash(message, 'error')
    
    return render_template('auth/register.html')


@auth_bp.route('/profile')
@login_required
def profile():
    """用户资料"""
    return render_template('auth/profile.html', user=current_user)


@auth_bp.route('/profile', methods=['PUT'])
@login_required
def update_profile():
    """更新用户资料"""
    data = request.get_json()
    
    try:
        if 'nickname' in data:
            current_user.nickname = data['nickname']
        if 'email' in data:
            current_user.email = data['email'] if data['email'] else None
        
        db.session.commit()
        return jsonify({'success': True, 'message': '资料更新成功'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'更新失败：{str(e)}'})


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """修改密码"""
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not current_password or not new_password:
        return jsonify({'success': False, 'message': '当前密码和新密码不能为空'})
    
    if not current_user.check_password(current_password):
        return jsonify({'success': False, 'message': '当前密码错误'})
    
    try:
        current_user.set_password(new_password)
        db.session.commit()
        return jsonify({'success': True, 'message': '密码修改成功'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'修改失败：{str(e)}'})


# API 路由
@auth_bp.route('/api/current-user')
@login_required
def api_current_user():
    """获取当前用户信息"""
    return jsonify({
        'success': True,
        'user': current_user.to_dict()
    })