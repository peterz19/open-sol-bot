import signal

from solbot_common.log import logger
from solbot_common.prestart import pre_start

from cache_preloader.services.auto_update_service import AutoUpdateCacheService
import sys
import asyncio
from functools import partial
async def main():
    """主函数"""
    pre_start()

    service = AutoUpdateCacheService()

    async def shutdown(service, sig):
        """异步关闭逻辑"""
        logger.info(f"Received signal {sig}, shutting down...")
        await service.stop()  # 假设 service 有异步 stop() 方法
        loop = asyncio.get_running_loop()
        loop.stop()

    def sync_signal_handler(service, sig, loop):
        """Windows 同步信号处理器 -> 触发异步关闭"""
        asyncio.run_coroutine_threadsafe(shutdown(service, sig), loop)
    def signal_handler():
        """信号处理函数"""
        logger.info("Received shutdown signal")
        # 使用 create_task 来避免阻塞信号处理
        stop_task = asyncio.create_task(service.stop())
        # 添加任务完成回调以处理可能的异常
        stop_task.add_done_callback(lambda t: t.exception() if t.exception() else None)

    # 注册信号处理
    loop = asyncio.get_running_loop()
    try:
        # Windows 使用 signal.signal()
        if sys.platform == "win32":
            for sig in (signal.SIGINT, signal.SIGBREAK):  # Windows 不支持 SIGTERM
                signal.signal(
                    sig,
                    partial(sync_signal_handler, service, sig, loop)
                )
        else:  # Unix/Linux 使用 loop.add_signal_handler()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig,
                    partial(asyncio.create_task, shutdown(service, sig))
                )

        await service.start()  # 启动服务

    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        raise
    finally:
        # 仅 Unix 需要移除信号处理器
        if sys.platform != "win32":
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.remove_signal_handler(sig)
    #
    # try:
    #     for sig in (signal.SIGTERM, signal.SIGINT):
    #         loop.add_signal_handler(sig, signal_handler)
    #
    #     # 启动服务并等待结束
    #     await service.start()
    # except Exception as e:
    #     logger.error(f"Fatal error in main: {e}")
    #     raise
    # finally:
    #     # 移除信号处理器
    #     for sig in (signal.SIGTERM, signal.SIGINT):
    #         loop.remove_signal_handler(sig)




if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise
