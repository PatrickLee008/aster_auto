"""
用户管理路由（管理员功能）
"""

from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from functools import wraps
from models import User
from models.base import db

users_bp = Blueprint('users', __name__, url_prefix='/users')


def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            if request.is_json:
                return jsonify({'success': False, 'message': '需要管理员权限'})
            flash('需要管理员权限', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


@users_bp.route('/')
@login_required
@admin_required
def index():
    """用户管理首页"""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('users/index.html', users=users)


@users_bp.route('/api/list')
@login_required
@admin_required
def api_list():
    """获取用户列表API"""
    try:
        users = User.query.order_by(User.created_at.desc()).all()
        user_list = []
        
        for user in users:
            user_data = user.to_dict()
            # 添加统计信息
            user_data['wallet_count'] = len(user.wallets)
            user_list.append(user_data)
        
        return jsonify({
            'success': True,
            'users': user_list
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@users_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    """创建用户"""
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        
        try:
            # 验证数据
            username = data.get('username')
            password = data.get('password')
            nickname = data.get('nickname')
            email = data.get('email', '')
            max_tasks = int(data.get('max_tasks', 5))
            is_admin = bool(data.get('is_admin', False))
            
            if not username or not password or not nickname:
                raise ValueError('用户名、密码和昵称不能为空')
            
            # 检查用户名是否已存在
            if User.query.filter_by(username=username).first():
                raise ValueError('用户名已存在')
            
            # 创建用户
            user = User(
                username=username,
                nickname=nickname,
                email=email if email else None,
                max_tasks=max_tasks,
                is_admin=is_admin
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            message = f'用户 {username} 创建成功'
            if request.is_json:
                return jsonify({'success': True, 'message': message})
            flash(message, 'success')
            return redirect(url_for('users.index'))
            
        except Exception as e:
            db.session.rollback()
            message = f'创建失败：{str(e)}'
            if request.is_json:
                return jsonify({'success': False, 'message': message})
            flash(message, 'error')
    
    return render_template('users/create.html')


@users_bp.route('/<int:user_id>')
@login_required
@admin_required
def detail(user_id):
    """用户详情"""
    user = User.query.get_or_404(user_id)
    return render_template('users/detail.html', user=user)


@users_bp.route('/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(user_id):
    """编辑用户"""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        
        try:
            # 更新基本信息
            if 'nickname' in data:
                user.nickname = data['nickname']
            if 'email' in data:
                user.email = data['email'] if data['email'] else None
            if 'max_tasks' in data:
                user.max_tasks = int(data['max_tasks'])
            if 'is_active' in data:
                user.account_enabled = bool(data['is_active'])
            if 'is_admin' in data and user.id != current_user.id:  # 不能修改自己的管理员权限
                user.is_admin = bool(data['is_admin'])
            
            # 如果提供了新密码，则更新密码
            if 'password' in data and data['password']:
                print(f"[DEBUG] 更新用户 {user.username} 的密码")
                print(f"[DEBUG] 旧密码哈希: {user.password_hash[:50]}...")
                user.set_password(data['password'])
                print(f"[DEBUG] 新密码哈希: {user.password_hash[:50]}...")
                # 立即验证新密码
                verify_result = user.check_password(data['password'])
                print(f"[DEBUG] 密码验证结果: {verify_result}")
                if not verify_result:
                    raise Exception("密码更新后验证失败，请检查密码哈希方法")
            
            db.session.commit()
            print(f"[DEBUG] 数据已提交到数据库")
            
            message = f'用户 {user.username} 更新成功'
            if request.is_json:
                return jsonify({'success': True, 'message': message})
            flash(message, 'success')
            return redirect(url_for('users.detail', user_id=user.id))
            
        except Exception as e:
            db.session.rollback()
            message = f'更新失败：{str(e)}'
            if request.is_json:
                return jsonify({'success': False, 'message': message})
            flash(message, 'error')
    
    return render_template('users/edit.html', user=user)


@users_bp.route('/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_status(user_id):
    """切换用户状态（启用/禁用）"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': '不能禁用自己的账户'})
    
    try:
        user.account_enabled = not user.account_enabled
        db.session.commit()
        
        status = '启用' if user.account_enabled else '禁用'
        return jsonify({'success': True, 'message': f'用户 {user.username} 已{status}'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@users_bp.route('/<int:user_id>/delete', methods=['DELETE'])
@login_required
@admin_required
def delete(user_id):
    """删除用户"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': '不能删除自己的账户'})
    
    try:
        username = user.username
        wallet_count = len(user.wallets)
        task_count = len(user.tasks)
        
        # 删除用户（级联删除钱包和任务）
        db.session.delete(user)
        db.session.commit()
        
        message = f'用户 {username} 已删除'
        if wallet_count > 0 or task_count > 0:
            message += f'，同时删除了 {wallet_count} 个钱包和 {task_count} 个任务'
        
        return jsonify({'success': True, 'message': message})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@users_bp.route('/<int:user_id>/reset-password', methods=['POST'])
@login_required
@admin_required
def reset_password(user_id):
    """重置用户密码"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    new_password = data.get('password')
    
    if not new_password:
        return jsonify({'success': False, 'message': '新密码不能为空'})
    
    try:
        print(f"[DEBUG RESET] 重置用户 {user.username} (ID:{user.id}) 的密码")
        print(f"[DEBUG RESET] 用户状态: account_enabled={user.account_enabled}")
        print(f"[DEBUG RESET] 旧密码哈希: {user.password_hash[:50]}...")
        
        # 重置密码
        user.set_password(new_password)
        
        print(f"[DEBUG RESET] 新密码哈希: {user.password_hash[:50]}...")
        
        # 立即验证新密码
        verify_result = user.check_password(new_password)
        print(f"[DEBUG RESET] 密码验证结果: {verify_result}")
        
        if not verify_result:
            raise Exception("密码重置后验证失败")
        
        db.session.commit()
        print(f"[DEBUG RESET] 密码已成功重置并提交到数据库")
        
        message = f'用户 {user.username} 密码已重置'
        if not user.account_enabled:
            message += ' (注意: 该用户已被禁用，可以登录但无法启动任务)'
        
        return jsonify({'success': True, 'message': message})
        
    except Exception as e:
        db.session.rollback()
        print(f"[DEBUG RESET] 密码重置失败: {e}")
        return jsonify({'success': False, 'message': str(e)})


@users_bp.route('/disable-all', methods=['POST'])
@login_required
@admin_required
def disable_all_users():
    """一键禁用所有用户（除了当前管理员自己）"""
    try:
        # 获取所有活跃用户（排除当前管理员）
        users_to_disable = User.query.filter(
            User.account_enabled == True,
            User.id != current_user.id
        ).all()
        
        if not users_to_disable:
            return jsonify({'success': False, 'message': '没有需要禁用的用户'})
        
        # 批量禁用用户
        disabled_count = 0
        disabled_usernames = []
        
        for user in users_to_disable:
            user.account_enabled = False
            disabled_count += 1
            disabled_usernames.append(user.username)
        
        db.session.commit()
        
        message = f'成功禁用 {disabled_count} 个用户：{", ".join(disabled_usernames[:5])}'
        if len(disabled_usernames) > 5:
            message += f' 等{len(disabled_usernames)}个用户'
        
        return jsonify({
            'success': True, 
            'message': message,
            'disabled_count': disabled_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'批量禁用失败: {str(e)}'})