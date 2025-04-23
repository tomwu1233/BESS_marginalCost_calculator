
from fastapi import FastAPI
from pydantic import BaseModel
from math import pow
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from fastapi import FastAPI
from pydantic import BaseModel
from math import sqrt, exp

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


# 👇 设置根路径访问 index.html
@app.get("/")
def read_root():
    return FileResponse(os.path.join("static", "index.html"))

class CostInput(BaseModel):
    mode: str  # "charge" or "discharge"
    soc_start: float  # e.g., 0.8
    soc_end: float    # e.g., 0.2
    efficiency_ch: float
    efficiency_dis: float
    voltage: float
    battery_capacity: float  # kWh, user-defined in model page
    cEnergy: float
    cCapacity: float
    OM_total: float
    N_cycle: int = 5000

@app.post("/calculate")
def calculate_cost(data: CostInput):
    # Step 1: calculate DoD
    soc_start = max(0.0, min(1.0, data.soc_start))
    soc_end = max(0.0, min(1.0, data.soc_end))
    dod = abs(soc_start - soc_end)

    # Step 2: calculate energy = DoD * battery capacity
    Q = dod * data.battery_capacity  # kWh

    # Step 3: degradation cost using new formula
    beta_0 = 4901
    beta_1 = 1.98
    beta_2 = 0.016
    if dod <= 0:
        return {"error": "Invalid SoC range or DoD = 0"}

    N_cycle = beta_0 * dod ** (-beta_1) * pow(2.71828, beta_2 * (1 - dod))
    degradation = data.cCapacity / N_cycle
    c_degradation = degradation * Q/2
    #假设充/放电的degradation是一个循环的一半

    # Step 4: energy loss cost
    if data.mode == "charge":
        loss = Q * (1 - data.efficiency_ch)
    elif data.mode == "discharge":
        loss = Q * (1 - data.efficiency_dis)
    else:
        return {"error": "Mode must be 'charge' or 'discharge'"}
    c_energy_loss = loss * data.cEnergy

    # Step 5: O&M cost
    om_unit = data.OM_total / (data.N_cycle * data.battery_capacity)
    om_cost = om_unit * Q

    # Step 6: auxiliary energy cost (fixed 250 kWh)
    aux_energy = 250000 / 5000000
    c_aux = (aux_energy * data.battery_capacity)/1000 * data.cEnergy

    total = c_degradation + c_energy_loss + om_cost + c_aux

    return {
        "Mode": data.mode,
        "SoC Start": soc_start,
        "SoC End": soc_end,
        "DoD (%)": round(dod * 100, 2),
        "Total Marginal Cost (€)": round(total, 4),
        "Degradation Cost (€)": round(c_degradation, 4),
        "Energy Loss Cost (€)": round(c_energy_loss, 4),
        "O&M Cost (€)": round(om_cost, 4),
        "Auxiliary Cost (€)": round(c_aux, 4)
    }
