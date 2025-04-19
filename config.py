import json
import os.path
from server_logger import ServerLogger

logger = ServerLogger()

class Config:
    def __init__(self):
        self.config = {}
    
    def get_json_config(self):
        return self.config
    
    # 检查设置文件
    def read_config_file(self,filename):
        if os.path.exists(filename):
            with open(filename, "r", encoding = "utf8") as file:
                self.config = json.load(file)
                logger.info("配置文件已读取")
        else:
            self.config = self._create_config_file(filename)
            logger.info("未找到配置文件，使用默认值创建")
    
    
    # 创建设置文件
    @staticmethod
    def _create_config_file(filename):
        config = {}
        config["ip"] = "0.0.0.0"
        config["port"] = 25565
        config["protocol"] = 2
        config["motd"] = "§c服务器正在维护！\n§e请等待服主通知"
        config["version_text"] = "§4服务器维护中..."
        config["kick_message"] = "§4§l很抱歉，服务器正在维护中，暂时无法进入！\n\n§e请不要心急，耐心等待服主通知"
        config["server_icon"] = "server-icon.png"
        config["samples"] = ["§f服务器正在维护", "§f请等待服主通知"]
        
        with open(filename, "w", encoding = "utf8") as file:
            json.dump(config, file, sort_keys=True, indent=4, ensure_ascii=False)
            logger.info("配置文件已写入")
        return config