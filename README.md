# MC_SLP
用于在停服维护过程对客户端提供SLP服务通知玩家服务器正在维护的微型服务器，全称：Minecraft Server List Ping

可以在配置文件内设置：
- 需要绑定的ip
- 需要绑定的port
- 服务器motd
- 玩家列表
- 版本名称
- 服务器图标文件
- 踢出消息

服务器启动会自动在"./logs/"下生成日志

使用：
1. 先下载源码
2. 在源码文件夹内，使用pip install -r requirements.txt安装依赖
3. 然后在当前文件夹下打开终端，使用命令python main.py运行即可
    - Windows用户可以双击start.bat启动

## TODO
None
