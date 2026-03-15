#!/bin/bash
#
# 技能每日推送定时任务
# 每天北京时间 18:00 推送技能推荐到飞书
#
# 安装定时任务:
#   ./skill-push.sh install
#
# 卸载定时任务:
#   ./skill-push.sh uninstall
#
# 手动触发推送:
#   ./skill-push.sh push
#
# 查看状态:
#   ./skill-push.sh status
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUSH_SCRIPT="${SCRIPT_DIR}/skill-push.py"
CRON_JOB="0 18 * * * cd ${SCRIPT_DIR} && /usr/bin/python3 ${PUSH_SCRIPT} --push >> /var/log/openclaw-skill-push.log 2>&1"

install_cron() {
    echo "安装技能推送定时任务..."
    
    # 检查是否已存在
    if crontab -l 2>/dev/null | grep -q "skill-push.py"; then
        echo "定时任务已存在，跳过安装"
        return
    fi
    
    # 添加定时任务
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    
    echo "✅ 定时任务已安装"
    echo "   执行时间: 每天 18:00 (北京时间)"
    echo "   日志文件: /var/log/openclaw-skill-push.log"
}

uninstall_cron() {
    echo "卸载技能推送定时任务..."
    
    # 移除定时任务
    crontab -l 2>/dev/null | grep -v "skill-push.py" | crontab - 2>/dev/null || true
    
    echo "✅ 定时任务已卸载"
}

show_status() {
    echo "=== 技能推送定时任务状态 ==="
    
    if crontab -l 2>/dev/null | grep -q "skill-push.py"; then
        echo "状态: ✅ 已安装"
        echo ""
        echo "定时任务:"
        crontab -l 2>/dev/null | grep "skill-push.py"
    else
        echo "状态: ❌ 未安装"
    fi
    
    echo ""
    echo "推送配置:"
    python3 "${PUSH_SCRIPT}" --show-config 2>/dev/null || echo "  未配置"
}

do_push() {
    echo "执行技能推送..."
    python3 "${PUSH_SCRIPT}" --push
}

case "${1:-status}" in
    install)
        install_cron
        ;;
    uninstall)
        uninstall_cron
        ;;
    push)
        do_push
        ;;
    status)
        show_status
        ;;
    *)
        echo "用法: $0 {install|uninstall|push|status}"
        exit 1
        ;;
esac
