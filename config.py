import json
import os.path
from server_logger import ServerLogger

logger = ServerLogger()

class Config:
    def __init__(self):
        self.config = {}
    
    def get_json_config(self):
        return self.config.copy()
    
    @staticmethod
    def get_default_config():
        return {
            "ip": "0.0.0.0",
            "port": 25565,
            "protocol": 2,
            "motd": "§c服务器正在维护！\n§e请等待服主通知",
            "version_text": "§4服务器维护中...",
            "kick_message": "§4§l很抱歉，服务器正在维护中，暂时无法进入！\n\n§e请不要心急，耐心等待服主通知",
            "server_icon": "server-icon.png",
            "samples": ["§f服务器正在维护", "§f请等待服主通知"]
        }
    
    def _use_temp_default(self):
        self.config = self.get_default_config()
        logger.warning("正在使用临时默认配置（不会修改原配置文件）")

    def _create_config_file(self, filename):
        default_config = self.get_default_config()
        try:
            with open(filename, "w", encoding="utf8") as file:
                json.dump(default_config, file,
                         sort_keys=True,
                         indent=4,
                         ensure_ascii=False)
                logger.info("已使用默认值创建新配置文件")
            self.config = default_config
        except IOError as e:
            logger.error(f"创建配置文件失败: {str(e)}")
            self._use_temp_default()#使用默认值
            return
    
    def read_config_file(self, filename):
        if not os.path.exists(filename):
            logger.warning("未找到配置文件")
            self._create_config_file(filename)
            return
        #找到配置文件，读取
        try:
            with open(filename, "r", encoding="utf8") as file:
                user_config = json.load(file)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"配置文件解析失败: {str(e)}")
            self._use_temp_default()
            return
        except Exception as e:
            logger.error(f"读取配置文件时发生意外错误: {str(e)}")
            self._use_temp_default()
            return

        default_config = self.get_default_config()
        validation_errors = []
        
        # 检查缺失项和类型错误
        for key, default_value in default_config.items():
            if key not in user_config:
                validation_errors.append(f"缺失必要配置项: '{key}'")
                continue
            
            user_value = user_config[key]
            if not isinstance(user_value, type(default_value)):
                expected_type = type(default_value).__name__
                actual_type = type(user_value).__name__
                validation_errors.append(
                    f"配置项 '{key}' 类型错误 - 需要: {expected_type}, 实际: {actual_type}"
                )

        if validation_errors:
            for error in validation_errors:
                logger.error(error)
            logger.error("配置文件验证失败")
            self._use_temp_default()
        else:
            self.config = user_config
            logger.info("配置文件验证通过并成功加载")