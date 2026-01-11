"""
系统配置API路由
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from functools import wraps

from models import SystemConfig
from models.base import db

config_bp = Blueprint('config', __name__, url_prefix='/api/config')


def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return jsonify({'success': False, 'message': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return decorated_function



@config_bp.route('/brightdata', methods=['GET'])
@login_required
@admin_required
def get_brightdata_config():
    """获取Bright Data配置"""
    try:
        enabled = SystemConfig.get_value('brightdata_enabled', False)
        
        return jsonify({
            'success': True,
            'enabled': enabled
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取配置失败: {str(e)}'
        }), 500


@config_bp.route('/brightdata', methods=['POST'])
@login_required
@admin_required
def update_brightdata_config():
    """更新Bright Data配置"""
    try:
        data = request.get_json()
        enabled = data.get('enabled', False)
        
        # 保存到数据库
        SystemConfig.set_value(
            'brightdata_enabled',
            enabled,
            config_type='boolean',
            description='Bright Data任务级代理开关'
        )
        

        
        status_text = '已启用' if enabled else '已禁用'
        
        return jsonify({
            'success': True,
            'message': f'Bright Data代理{status_text}',
            'enabled': enabled
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'更新配置失败: {str(e)}'
        }), 500


@config_bp.route('/all', methods=['GET'])
@login_required
@admin_required
def get_all_configs():
    """获取所有系统配置"""
    try:
        configs = SystemConfig.get_all_configs()
        
        # 添加代理状态
        brightdata_enabled = SystemConfig.get_value('brightdata_enabled', False)
        
        return jsonify({
            'success': True,
            'configs': configs,
            'brightdata_enabled': brightdata_enabled
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取配置失败: {str(e)}'
        }), 500
