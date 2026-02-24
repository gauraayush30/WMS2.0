"""
Replenishment recommendation engine.
Calculates optimal replenishment orders based on forecasted demand and inventory parameters.
"""

from datetime import date, timedelta
from typing import Optional


class ReplenishmentRecommendationEngine:
    """
    Calculates replenishment recommendations based on:
    - Current stock level
    - Forecasted demand
    - Lead time
    - Safety stock
    - Reorder point
    - Target stock level
    - Minimum order quantity
    """

    @staticmethod
    def calculate_recommendation(
        current_stock: int,
        forecasted_demand_days: list[float],
        lead_time_days: int,
        min_order_qty: int,
        reorder_point: int,
        safety_stock: int,
        target_stock_level: int,
    ) -> dict:
        """
        Calculate replenishment recommendation.

        Args:
            current_stock: Current inventory level
            forecasted_demand_days: List of daily forecasted sales (future N days)
            lead_time_days: Days until supplier delivers order
            min_order_qty: Minimum order quantity from supplier
            reorder_point: Stock level that triggers reorder
            safety_stock: Minimum buffer stock to maintain
            target_stock_level: Desired inventory level

        Returns:
            Dictionary with recommendation details
        """
        # Calculate demand during and after lead time
        # The critical period is: today + lead_time_days
        days_to_check = min(lead_time_days + 7, len(forecasted_demand_days))
        demand_during_lead_time = sum(forecasted_demand_days[:days_to_check])

        # Project stock at end of lead time
        projected_stock = current_stock - demand_during_lead_time

        # Determine if reorder is needed
        reorder_needed = projected_stock <= reorder_point

        # Calculate recommended order quantity
        if reorder_needed:
            # Order enough to reach target stock level + safety buffer
            units_needed = max(0, target_stock_level - projected_stock + safety_stock)

            # Round up to nearest min_order_qty multiple
            if units_needed > 0:
                order_qty = (
                    ((units_needed + min_order_qty - 1) // min_order_qty)
                    * min_order_qty
                )
            else:
                order_qty = 0

            # Determine urgency
            if projected_stock < safety_stock:
                urgency = "CRITICAL"
            elif projected_stock < reorder_point:
                urgency = "HIGH"
            else:
                urgency = "MEDIUM"

            order_date = date.today()
        else:
            order_qty = 0
            urgency = "LOW"
            order_date = None

        return {
            "reorder_needed": reorder_needed,
            "order_quantity": int(order_qty),
            "urgency": urgency,
            "projected_stock_at_lead_time": int(projected_stock),
            "current_stock": current_stock,
            "demand_during_lead_time": round(demand_during_lead_time, 2),
            "reorder_point": reorder_point,
            "safety_stock": safety_stock,
            "target_stock_level": target_stock_level,
            "suggested_order_date": order_date.strftime("%Y-%m-%d") if order_date else None,
            "expected_arrival_date": (
                (date.today() + timedelta(days=lead_time_days)).strftime("%Y-%m-%d")
                if reorder_needed and order_qty > 0
                else None
            ),
            "message": ReplenishmentRecommendationEngine._get_message(
                reorder_needed, urgency, projected_stock, order_qty
            ),
        }

    @staticmethod
    def _get_message(reorder_needed: bool, urgency: str, projected_stock: int, order_qty: int) -> str:
        """Generate human-readable recommendation message."""
        if not reorder_needed:
            return f"No reorder needed. Projected stock in lead time: {projected_stock} units."

        msgs = {
            "CRITICAL": f"⚠️ CRITICAL: Projected stock will drop to {projected_stock} units. Order {order_qty} units immediately!",
            "HIGH": f"⚠️ HIGH PRIORITY: Projected stock will be {projected_stock} units. Recommend ordering {order_qty} units.",
            "MEDIUM": f"Order recommendation: {order_qty} units to maintain target stock level.",
        }
        return msgs.get(urgency, "Review replenishment settings.")
