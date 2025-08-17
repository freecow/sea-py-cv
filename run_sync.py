#!/usr/bin/env python3
"""
快速同步演示脚本 - 支持多配置文件和Token参数
支持.env文件配置和命令行参数
"""

import asyncio
import json
import logging
import argparse
import os
from dotenv import load_dotenv
from fast_sync import FastSync
from seatable_official_adapter import SeaTableOfficialAdapter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_env_config():
    """加载.env文件配置"""
    # 加载.env文件
    load_dotenv()
    
    return {
        'token': os.getenv('SEATABLE_TOKEN'),
        'server_url': os.getenv('SEATABLE_SERVER_URL', 'https://cloud.seatable.cn'),
        'config_file': os.getenv('SEATABLE_CONFIG_FILE', 'config/sync_rules.json'),
        'max_concurrent': int(os.getenv('SEATABLE_MAX_CONCURRENT', '5'))
    }

def parse_arguments():
    """解析命令行参数"""
    # 先加载环境变量作为默认值
    env_config = load_env_config()
    
    parser = argparse.ArgumentParser(
        description="SeaTable数据同步工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 使用.env文件配置
  python run_sync.py
  
  # 命令行参数（会覆盖.env文件中的配置）
  python run_sync.py --config config/sync_rules.json --token YOUR_TOKEN
  python run_sync.py --config config/another_config.json --token ANOTHER_TOKEN
  python run_sync.py -c config/test_config.json -t TEST_TOKEN
  
配置优先级: 命令行参数 > .env文件 > 默认值

.env文件示例:
  SEATABLE_TOKEN=your_api_token_here
  SEATABLE_SERVER_URL=https://cloud.seatable.cn
  SEATABLE_CONFIG_FILE=config/sync_rules.json
  SEATABLE_MAX_CONCURRENT=5
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        default=env_config['config_file'],
        help=f'同步配置文件路径 (默认: {env_config["config_file"]})'
    )
    
    parser.add_argument(
        '--token', '-t',
        type=str,
        default=env_config['token'],
        help='SeaTable API Token (可从.env文件读取)'
    )
    
    parser.add_argument(
        '--server-url', '-s',
        type=str,
        default=env_config['server_url'],
        help=f'SeaTable服务器URL (默认: {env_config["server_url"]})'
    )
    
    parser.add_argument(
        '--max-concurrent',
        type=int,
        default=env_config['max_concurrent'],
        help=f'最大并发请求数 (默认: {env_config["max_concurrent"]})'
    )
    
    return parser.parse_args()

async def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()
    
    # 检查Token是否提供
    if not args.token:
        logger.error("错误: 必须提供SeaTable API Token")
        logger.error("请通过以下任一方式提供Token:")
        logger.error("1. 命令行: python run_sync.py --token YOUR_TOKEN")
        logger.error("2. .env文件: SEATABLE_TOKEN=your_api_token_here")
        return
    
    logger.info(f"开始快速同步演示...")
    logger.info(f"配置文件: {args.config}")
    logger.info(f"服务器URL: {args.server_url}")
    logger.info(f"最大并发数: {args.max_concurrent}")
    
    # 检查配置文件是否存在
    if not os.path.exists(args.config):
        logger.error(f"配置文件不存在: {args.config}")
        return
    
    # 1. 创建SeaTable适配器
    adapter = SeaTableOfficialAdapter(
        server_url=args.server_url,
        api_token=args.token
    )
    
    # 2. 测试连接
    try:
        await adapter.test_connection()
        logger.info("SeaTable连接成功")
    except Exception as e:
        logger.error(f"SeaTable连接失败: {e}")
        return
    
    # 3. 加载同步规则与数据字典
    try:
        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)
        sync_rules = config['sync_rules']
        data_dictionary = config.get('data_dictionary', {})
        # 将latest_aggregation_config合并到data_dictionary中，以便FastSync能访问
        if 'latest_aggregation_config' in config:
            data_dictionary['latest_aggregation_config'] = config['latest_aggregation_config']
        logger.info(f"加载同步规则: {len(sync_rules)} 条")
    except Exception as e:
        logger.error(f"加载同步规则失败: {e}")
        return
    
    # 4. 运行快速同步（传入数据字典以正确解析日期等变量）
    try:
        from fast_sync import run_fast_sync
        # 使用用户指定的并发数
        await run_fast_sync(adapter, sync_rules, data_dictionary=data_dictionary, max_concurrent=args.max_concurrent)
        logger.info("快速同步完成！")
    except Exception as e:
        logger.error(f"快速同步失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())
