"""
钱包控制器
处理钱包管理相关的API
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from services import WalletService

wallet_bp = Blueprint('wallet', __name__, url_prefix='/api/wallets')


@wallet_bp.route('', methods=['POST'])
@login_required
def add_wallet():
    """添加钱包API"""
    try:
        data = request.form.to_dict()
        
        # 检查钱包类型和配置
        wallet_type = data.get('wallet_type')
        has_spot_config = data.get('spot_api_key') and data.get('spot_secret_key')
        has_futures_config = data.get('user_address') and data.get('signer_address') and data.get('private_key')
        
        if wallet_type == 'unified' or (has_spot_config and has_futures_config):
            # 使用新的统一钱包创建方法
            # 移除重复的参数，避免冲突
            clean_data = {k: v for k, v in data.items() if k not in ['name', 'description', 'is_active']}
            
            success, message, wallets = WalletService.create_unified_wallet(
                user_id=current_user.id,
                name=data.get('name', '钱包配置'),
                description=data.get('description', ''),
                is_active=data.get('is_active', 'true').lower() in ['true', 'on', '1'],
                **clean_data
            )
            
            wallet_ids = [w.id for w in wallets] if wallets else []
            
            return jsonify({
                'success': success,
                'message': message,
                'wallet_ids': wallet_ids,
                'wallet_count': len(wallet_ids)
            })
        else:
            # 兼容旧的单一钱包类型创建方式
            success, message, wallet = WalletService.create_wallet(
                user_id=current_user.id,
                name=data.get('name'),
                wallet_type=data.get('wallet_type'),
                description=data.get('description'),
                api_key=data.get('api_key'),
                secret_key=data.get('secret_key'),
                user_address=data.get('user_address'),
                signer_address=data.get('signer_address'),
                private_key=data.get('private_key')
            )
            
            return jsonify({
                'success': success,
                'message': message,
                'wallet_id': wallet.id if wallet else None
            })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"添加钱包异常: {str(e)}"
        }), 500


@wallet_bp.route('/<int:wallet_id>/test', methods=['POST'])
@login_required
def test_wallet(wallet_id):
    """测试钱包连接API"""
    try:
        success, message, balance_info = WalletService.test_wallet_connection(wallet_id, current_user.id)
        
        return jsonify({
            'success': success,
            'message': message,
            'balance_info': balance_info
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"连接测试异常: {str(e)}",
            'balance_info': None
        }), 500


@wallet_bp.route('/<int:wallet_id>', methods=['PUT', 'POST'])
@login_required
def update_wallet(wallet_id):
    """更新钱包API"""
    try:
        # 支持表单数据和JSON数据
        if request.content_type and 'application/json' in request.content_type:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
        # 处理布尔值转换
        if 'is_active' in data:
            data['is_active'] = data['is_active'] in ['true', 'on', '1', True]
        
        # 移除可能重复的 wallet_id 字段
        data.pop('wallet_id', None)
        
        success, message = WalletService.update_wallet(
            wallet_id=wallet_id,
            user_id=current_user.id,
            **data
        )
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"更新钱包异常: {str(e)}"
        }), 500


@wallet_bp.route('/<int:wallet_id>', methods=['DELETE'])
@login_required
def delete_wallet(wallet_id):
    """删除钱包API"""
    try:
        success, message = WalletService.delete_wallet(wallet_id, current_user.id)
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"删除钱包异常: {str(e)}"
        }), 500


@wallet_bp.route('', methods=['GET'])
@login_required
def get_wallets():
    """获取钱包列表API"""
    try:
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        wallets = WalletService.get_user_wallets(current_user.id, include_inactive)
        
        wallet_list = []
        for wallet in wallets:
            wallet_data = {
                'id': wallet.id,
                'name': wallet.name,
                'description': wallet.description,
                'wallet_type': wallet.wallet_type,
                'is_active': wallet.is_active,
                'created_at': wallet.created_at.isoformat(),
                'last_used': wallet.last_used.isoformat() if wallet.last_used else None,
                'masked_credentials': wallet.get_masked_credentials()
            }
            wallet_list.append(wallet_data)
        
        return jsonify({
            'success': True,
            'wallets': wallet_list
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"获取钱包列表异常: {str(e)}"
        }), 500


@wallet_bp.route('/<int:wallet_id>', methods=['GET'])
@login_required
def get_wallet(wallet_id):
    """获取单个钱包信息API"""
    try:
        wallet = WalletService.get_wallet_by_id(wallet_id, current_user.id)
        
        if not wallet:
            return jsonify({
                'success': False,
                'message': '钱包不存在'
            }), 404
        
        wallet_data = {
            'id': wallet.id,
            'name': wallet.name,
            'description': wallet.description,
            'wallet_type': wallet.wallet_type,
            'is_active': wallet.is_active,
            'created_at': wallet.created_at.isoformat(),
            'last_used': wallet.last_used.isoformat() if wallet.last_used else None,
            'user_address': wallet.user_address,
            'signer_address': wallet.signer_address,
            'masked_credentials': wallet.get_masked_credentials()
        }
        
        return jsonify({
            'success': True,
            'wallet': wallet_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"获取钱包信息异常: {str(e)}"
        }), 500