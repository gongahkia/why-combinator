from dataclasses import dataclass
from typing import List, Optional, Union, Dict
import math
import time
from why_combinator.models import InteractionLog, MarketParams, UnitEconomics, FundingState

def calculate_adoption_rate(params: MarketParams, tick_count: int) -> float:
    """Calculate adoption rate using logistic S-curve."""
    k = (params.viral_coefficient * 0.5) + (params.conversion_rate * 2.0)
    k *= params.growth_modifier
    t0 = params.inflection_tick
    try:
        return 1.0 / (1.0 + math.exp(-k * (tick_count - t0)))
    except OverflowError:
        return 0.0 if (tick_count - t0) < 0 else 1.0

def calculate_churn_rate(interactions: List[InteractionLog], tick_count: int, retention_half_life: float) -> float:
    """Calculate churn rate using cohort-based retention decay."""
    if not interactions:
        return 0.0
        
    start_time = interactions[0].timestamp
    end_time = interactions[-1].timestamp
    duration = end_time - start_time
    
    if duration <= 0:
        ticks_per_sec = 1.0
    else:
        ticks_per_sec = tick_count / duration
        
    agent_start_times = {}
    for i in interactions:
        if i.agent_id not in agent_start_times:
            agent_start_times[i.agent_id] = i.timestamp
            
    expected_active_sum = 0.0
    current_time_ref = end_time
    
    for aid, start_ts in agent_start_times.items():
        age_seconds = current_time_ref - start_ts
        age_ticks = age_seconds * ticks_per_sec
        survival_prob = 0.5 ** (age_ticks / retention_half_life)
        expected_active_sum += survival_prob
        
    return 1.0 - (expected_active_sum / len(agent_start_times)) if agent_start_times else 0.0

def calculate_product_quality(interactions: List[InteractionLog]) -> float:
    """Calculate product quality score (0.0 - 1.0) based on interaction sentiment."""
    positive_actions = {"buy", "invest", "partner", "collaborate"}
    negative_actions = {"complain", "sell", "criticize", "ignore"}
    
    positive_interactions = sum(1 for i in interactions if i.action in positive_actions)
    negative_interactions = sum(1 for i in interactions if i.action in negative_actions)
    total_relevant = positive_interactions + negative_interactions
    
    if total_relevant > 0:
        return positive_interactions / total_relevant
    else:
        return 0.5 # Neutral baseline

def calculate_market_share(interactions: List[InteractionLog], params: MarketParams) -> float:
    """Calculate market share based on relative quality."""
    my_quality_score = calculate_product_quality(interactions)
        
    if params.competitor_count == 0:
         return 1.0
    else:
         total_quality_pool = my_quality_score + (params.competitor_count * params.competitor_quality_avg)
         return my_quality_score / total_quality_pool if total_quality_pool > 0 else 0.0

def calculate_revenue_metrics(
    interactions: List[InteractionLog], 
    tick_count: int, 
    price: float, 
    model: str = "transactional"
) -> Dict[str, float]:
    """Calculate monthly revenue, cumulative revenue, and new monthly customers."""
    buy_interactions = [i for i in interactions if i.action == "buy"]
    buy_count_total = len(buy_interactions)
    
    monthly_new_customers = (buy_count_total / max(tick_count, 1)) * 30
    
    cumulative_revenue = 0.0
    monthly_revenue = 0.0
    
    if model == "transactional":
        cumulative_revenue = buy_count_total * price
        monthly_revenue = monthly_new_customers * price
        
    elif model in ("subscription", "freemium"):
        if not interactions:
             ticks_per_sec = 1.0
        else:
             duration = interactions[-1].timestamp - interactions[0].timestamp
             ticks_per_sec = tick_count / duration if duration > 0 else 1.0
        
        seconds_per_month = 30 * (1.0 / ticks_per_sec) if ticks_per_sec else 1.0
        sim_end_time = interactions[-1].timestamp if interactions else time.time()
        
        for i in buy_interactions:
            months_active = (sim_end_time - i.timestamp) / seconds_per_month
            if months_active < 0: months_active = 0
            cumulative_revenue += months_active * price
            
        sell_interactions = [i for i in interactions if i.action in ("sell", "cancel")]
        for i in sell_interactions:
             months_inactive = (sim_end_time - i.timestamp) / seconds_per_month
             if months_inactive < 0: months_inactive = 0
             cumulative_revenue -= months_inactive * price
             
        if cumulative_revenue < 0: cumulative_revenue = 0
        
        current_subs = len(buy_interactions) - len(sell_interactions)
        if current_subs < 0: current_subs = 0
        monthly_revenue = current_subs * price

    return {
        "monthly_revenue": monthly_revenue,
        "cumulative_revenue": cumulative_revenue,
        "monthly_new_customers": monthly_new_customers
    }

def calculate_burn_rate(
    econ: UnitEconomics, 
    monthly_revenue: float, 
    monthly_new_customers: float, 
    interactions: List[InteractionLog]
) -> float:
    """Calculate monthly burn rate using unit economics."""
    cogs = monthly_revenue * (1 - econ.gross_margin)
    marketing_spend = monthly_new_customers * econ.cac
    variable_opex = monthly_revenue * econ.opex_ratio
    
    burn_rate = econ.base_opex + cogs + marketing_spend + variable_opex
    
    # Morale factor
    employee_actions = [i for i in interactions if i.action in ("complain", "wait") and "employee" in str(i.outcome).lower()]
    morale_factor = 1.0 + len(employee_actions) * 0.001 
    burn_rate *= morale_factor
    
    return burn_rate

def calculate_runway(
    funding: FundingState, 
    current_burn_rate: float, 
    current_monthly_revenue: float, 
    cumulative_burn_approx: float,
    current_cumulative_revenue: float,
    tick_count: int
) -> float:
    """Calculate runway months using iterative growth model."""
    months_elapsed = max(tick_count / 30, 1)
    # Re-calculate cumulative burn if not provided? 
    # The caller provides approximation or we assume constant. 
    # Wait, the caller (generation.py) calculated cumulative_burn = burn_rate * months.
    # We'll take current_cash directly to be cleaner? No, funding state has initial.
    
    current_cash = funding.initial_capital - cumulative_burn_approx + current_cumulative_revenue
    
    if current_cash <= 0:
        return 0.0
        
    sim_runway = 0
    temp_cash = current_cash
    sim_revenue = current_monthly_revenue
    sim_burn = current_burn_rate
    
    while temp_cash > 0 and sim_runway < 60:
        sim_runway += 1
        sim_revenue *= (1 + funding.revenue_growth_rate)
        sim_burn *= (1 + funding.burn_growth_rate)
        net_burn = sim_burn - sim_revenue
        temp_cash -= net_burn
        
    return float(sim_runway)
