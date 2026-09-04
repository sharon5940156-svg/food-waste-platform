import type {Batch,Forecast,Product,Sales,TelemetryReading} from "../types";
const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
async function request<T>(path:string, init?:RequestInit):Promise<T>{
  const r=await fetch(`${BASE}${path}`,{...init,headers:{"Content-Type":"application/json",...(init?.headers||{})}});
  if(!r.ok){let detail=r.statusText;try{const j=await r.json();detail=j.detail||detail}catch{};throw new Error(detail)}
  return r.json();
}
export const api={
  health:()=>request<{status:string}>("/health"),
  products:()=>request<Product[]>("/products"),
  batches:()=>request<Batch[]>("/batches"),
  fefo:()=>request<Batch[]>("/batches/fefo"),
  telemetry:(id:number)=>request<TelemetryReading[]>(`/batches/${id}/telemetry`),
  forecast:(id:number)=>request<Forecast>(`/batches/${id}/forecast`),
  sales:(id:number)=>request<Sales[]>(`/products/${id}/sales`),
  ingestTelemetry:(body:{batch_id:number;temperature_c:number;humidity:number;time?:string})=>
    request<TelemetryReading>("/telemetry",{method:"POST",body:JSON.stringify(body)}),
  createSales:(body:{product_id:number;date:string;units_sold:number})=>
    request<Sales>("/sales",{method:"POST",body:JSON.stringify(body)})
};