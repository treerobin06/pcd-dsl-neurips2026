#!/bin/bash
# Overleaf 双向同步脚本
# 用法: bash sync_overleaf.sh [push|pull|sync]
#   push - 本地 → Overleaf
#   pull - Overleaf → 本地
#   sync - 先 pull 再 push（双向）

PAPER_DIR="$(cd "$(dirname "$0")" && pwd)"
SYNC_DIR="$PAPER_DIR/overleaf-sync"
FILES_TO_SYNC="main.tex references.bib neurips_2026.sty"

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

push_to_overleaf() {
    echo -e "${GREEN}[Push] 本地 → Overleaf${NC}"
    for f in $FILES_TO_SYNC; do
        if [ -f "$PAPER_DIR/$f" ]; then
            cp "$PAPER_DIR/$f" "$SYNC_DIR/$f"
            echo "  复制: $f"
        fi
    done
    cd "$SYNC_DIR"
    git add -A
    if git diff --cached --quiet; then
        echo "  无变更，跳过"
    else
        git commit -m "Sync from local $(date '+%Y-%m-%d %H:%M')"
        git push
        echo -e "${GREEN}  Push 成功${NC}"
    fi
}

pull_from_overleaf() {
    echo -e "${GREEN}[Pull] Overleaf → 本地${NC}"
    cd "$SYNC_DIR"
    git pull --rebase
    for f in $FILES_TO_SYNC; do
        if [ -f "$SYNC_DIR/$f" ]; then
            cp "$SYNC_DIR/$f" "$PAPER_DIR/$f"
            echo "  更新: $f"
        fi
    done
    echo -e "${GREEN}  Pull 成功${NC}"
}

case "${1:-sync}" in
    push)
        push_to_overleaf
        ;;
    pull)
        pull_from_overleaf
        ;;
    sync)
        pull_from_overleaf
        echo ""
        push_to_overleaf
        ;;
    *)
        echo "用法: bash sync_overleaf.sh [push|pull|sync]"
        exit 1
        ;;
esac
