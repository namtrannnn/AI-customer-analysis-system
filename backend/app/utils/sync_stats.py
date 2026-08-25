"""
Script CLI để đồng bộ dữ liệu thống kê hàng ngày (PB06 - BE-4)

Cách sử dụng:
  # Đồng bộ dữ liệu của ngày hôm nay
  python -m app.utils.sync_stats

  # Đồng bộ dữ liệu của một ngày cụ thể
  python -m app.utils.sync_stats --date 2026-07-10

  # Đồng bộ dữ liệu N ngày gần nhất
  python -m app.utils.sync_stats --days 7
"""

import argparse
import sys
from datetime import date, timedelta

# Đảm bảo import đúng khi chạy từ thư mục gốc backend
sys.path.insert(0, ".")

from app.database.session import SessionLocal
from app.routers.daily_statistics_router import _sync_date


def main():
    parser = argparse.ArgumentParser(description="Đồng bộ dữ liệu thống kê hàng ngày")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Ngày cần đồng bộ (định dạng YYYY-MM-DD). Mặc định: hôm nay",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Đồng bộ N ngày gần nhất (bao gồm hôm nay)",
    )
    args = parser.parse_args()

    db = SessionLocal()

    try:
        if args.days:
            # Đồng bộ N ngày gần nhất
            today = date.today()
            dates = [today - timedelta(days=i) for i in range(args.days)]
            dates.reverse()  # Sắp xếp từ cũ đến mới

            print(f"[SYNC] Dong bo {args.days} ngay gan nhat...")
            for d in dates:
                record = _sync_date(db, d)
                print(f"  [OK] {d.isoformat()} - {record.total_visitors} khach, {record.total_orders} don")

        elif args.date:
            # Đồng bộ một ngày cụ thể
            target = date.fromisoformat(args.date)
            print(f"[SYNC] Dong bo ngay {target.isoformat()}...")
            record = _sync_date(db, target)
            print(f"  [OK] {record.total_visitors} khach, {record.new_visitors} moi, {record.total_orders} don")

        else:
            # Mặc định: đồng bộ ngày hôm nay
            today = date.today()
            print(f"[SYNC] Dong bo ngay hom nay ({today.isoformat()})...")
            record = _sync_date(db, today)
            print(f"  [OK] {record.total_visitors} khach, {record.new_visitors} moi, {record.total_orders} don")

        print("[SUCCESS] Hoan tat!")

    except Exception as e:
        print(f"[ERROR] Loi: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
