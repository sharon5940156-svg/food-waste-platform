export interface Product { id:number; name:string; base_shelf_life_days:number; optimal_temp_c:number }
export interface Batch { id:number; product_id:number; quantity_kg:number; production_date:string; expiry_date:string; current_status:string }
export interface TelemetryReading { time:string; batch_id:number|null; temperature_c:number|null; humidity:number|null; spoilage_risk_score:number|null }
export interface Sales { id:number; product_id:number; date:string; units_sold:number }
export interface DemandEvaluation { mae:number; wmape:number; forecast_bias:number; pinball_loss_q10:number; pinball_loss_q50:number; pinball_loss_q90:number; asymmetric_loss:number; test_period_days:number }
export interface BurnoutPoint { day:number; predicted_demand:number; dynamic_spoilage:number; remaining_stock:number }
export interface Forecast {
  batch_id:number; product_id:number; product_name:string; remaining_shelf_life_days:number;
  spoilage_risk_score:number; predicted_temperature_c:number; forecast_method:string; sample_count:number;
  current_status:string; demand_forecast_7d:number[]; model_evaluation:DemandEvaluation|null;
  burnout_timeline:BurnoutPoint[]; predicted_waste_units:number; production_recommendation:number;
  lead_time_days:number; dynamic_rop:number
}