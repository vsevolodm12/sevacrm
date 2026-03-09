import calendar
from datetime import date, datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.models import Client, Payment

HISTORY_START_YEAR = 2026
HISTORY_START_MONTH = 2

MONTH_NAMES = ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"]


class StatsService:
    def _clients_for_month(self, db, month, year):
        """Активные клиенты, чья дата начала <= конца этого месяца"""
        active_clients = db.query(Client).filter(Client.is_active == True).all()
        last_day = calendar.monthrange(year, month)[1]
        target_dt = datetime(year, month, last_day, 23, 59, 59)
        return [
            c for c in active_clients
            if c.start_date is None or c.start_date <= target_dt
        ]

    def _get_payments_split(self, db, payments):
        """Возвращает (my_paid, partner_paid, my_pending) из списка Payment"""
        my_paid = 0.0
        partner_paid = 0.0
        my_pending = 0.0
        for p in payments:
            client = db.query(Client).filter(Client.id == p.client_id).first()
            has_partner = client and client.partner_id is not None
            amount = float(p.amount)
            if p.is_paid:
                if has_partner:
                    my_paid += amount / 2
                    partner_paid += amount / 2
                else:
                    my_paid += amount
            else:
                if has_partner:
                    my_pending += amount / 2
                else:
                    my_pending += amount
        return my_paid, partner_paid, my_pending

    def get_dashboard_stats(self, db: Session, month: int, year: int) -> Dict[str, Any]:
        relevant_clients = self._clients_for_month(db, month, year)
        monthly_maintenance_total = sum(float(c.monthly_fee or 0) for c in relevant_clients)

        payments = db.query(Payment).filter(Payment.month == month, Payment.year == year).all()
        my_paid, partner_paid, my_pending = self._get_payments_split(db, payments)

        return {
            "active_clients_count": len(relevant_clients),
            "monthly_maintenance_total": monthly_maintenance_total,
            "monthly_maintenance_paid": my_paid,
            "monthly_maintenance_pending": my_pending,
            "partner_paid": partner_paid,
            "active_projects_count": 0,
            "month_projects_earned": 0,
            "month_projects_pending": 0,
            "total_month_income": my_paid,
        }

    def _completed_orders_for_month(self, db, month, year):
        """Завершённые заказы, чья дата завершения попадает в данный месяц"""
        completed = db.query(Client).filter(Client.is_completed == True).all()
        result = []
        for c in completed:
            # Определяем месяц завершения: end_date → completed_at → created_at
            ref_dt = c.end_date or c.completed_at or c.created_at
            if ref_dt and ref_dt.month == month and ref_dt.year == year:
                result.append(c)
        return result

    def get_all_monthly_history(self, db: Session) -> List[Dict[str, Any]]:
        today = date.today()
        result = []
        year = HISTORY_START_YEAR
        month = HISTORY_START_MONTH

        while (year < today.year) or (year == today.year and month <= today.month):
            payments = db.query(Payment).filter(
                Payment.month == month, Payment.year == year
            ).all()

            my_income, partner_income, _ = self._get_payments_split(db, payments)

            result.append({
                "month": month,
                "year": year,
                "label": f"{MONTH_NAMES[month-1]} {year}",
                "my_income": my_income,
                "partner_income": partner_income,
                "total_income": my_income + partner_income,
            })

            month += 1
            if month > 12:
                month = 1
                year += 1

        return result

    def get_all_time_totals(self, db: Session) -> Dict[str, Any]:
        history = self.get_all_monthly_history(db)
        return {
            "my_total": sum(r["my_income"] for r in history),
            "partner_total": sum(r["partner_income"] for r in history),
            "grand_total": sum(r["total_income"] for r in history),
        }

    def get_monthly_history(self, db: Session, months: int = 12) -> List[Dict[str, Any]]:
        return self.get_all_monthly_history(db)


stats_service = StatsService()
