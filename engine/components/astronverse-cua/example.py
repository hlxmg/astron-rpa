"""
示例：如何使用ComputerUseAgent

使用方法:
1. 设置环境变量: export ARK_API_KEY="your_api_key"
2. 运行脚本: python example.py
"""

from astronverse.cua.computer_use import ComputerUseAgent
import os


def main():
    """示例主函数"""
    # 从命令行参数或默认值获取指令
    import sys

    if len(sys.argv) > 1:
        instruction = " ".join(sys.argv[1:])
    else:
        instruction = "打开计算器并计算 123 + 456"

    # 创建Agent（API Key从环境变量读取）
    agent = ComputerUseAgent(
        api_key=os.getenv("ARK_API_KEY"),  # 从环境变量ARK_API_KEY读取
        model="doubao-1-5-ui-tars-250428",
        language="Chinese",
        max_steps=20,
    )

    # 运行任务
    result = agent.run(instruction)

    # 打印结果
    print("\n" + "=" * 60)
    print("执行结果:")
    print(f"  成功: {result['success']}")
    print(f"  步数: {result['steps']}")
    print(f"  有效动作步数: {result['action_steps']}")
    print(f"  耗时: {result['duration']:.2f}秒")
    if result.get("error"):
        print(f"  错误: {result['error']}")
    print(f"  截图目录: {agent.screenshot_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
