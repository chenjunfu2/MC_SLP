import traceback

from server_logger import ServerLogger
from config import Config
from slp_server import SlpServer

logger = ServerLogger()

def main():
    config = Config()
    config.read_config_file("./slp_config.json")
    #logger.info(f"config:{config.get_json_config()}")
    
    slp_server = SlpServer(config.get_json_config())
    slp_server.start(True)
    
    return 0


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"发生错误: {traceback.format_exc()}")