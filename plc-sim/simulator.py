
import time
import random
import http.client

# InfluxDB Configuration
INFLUXDB_HOST = "influxdb"
INFLUXDB_PORT = 8086
INFLUXDB_ORG = "infm"
INFLUXDB_BUCKET = "timeseries"
INFLUXDB_TOKEN = "password"

# Water Level Sensor
class WaterLevelSensor:
    def __init__(self, sensor_id, initial_level=50.0):
        self.sensor_id = sensor_id
        self.water_level = initial_level

    def measure(self):
        noise = random.uniform(-0.5, 0.5)
        return max(0.0, min(100.0, self.water_level + noise))

    def update_level(self, delta):
        self.water_level = max(0.0, min(100.0, self.water_level + delta))


# Water Temperature Sensor
class WaterTemperatureSensor:
    def __init__(self, sensor_id, initial_temp=25.0):
        self.sensor_id = sensor_id
        self.temperature = initial_temp

    def measure(self):
        noise = random.uniform(-0.5, 0.5)
        return max(0.0, min(100.0, self.temperature + noise))

    def update_temperature(self, delta):
        self.temperature = max(0.0, min(100.0, self.temperature + delta))

    def get_id(self):
        return self.sensor_id


# Heater Actuator
class HeaterActuator:
    def __init__(self, actuator_id, initial_state="off"):
        self.actuator_id = actuator_id
        self.state = initial_state  # "on" or "off"

    def turn_on(self):
        self.state = "on"

    def turn_off(self):
        self.state = "off"


# Valve Actuator
class ValveActuator:
    def __init__(self, actuator_id, initial_state="closed"):
        self.actuator_id = actuator_id
        self.state = initial_state  # "open" or "closed"

    def open(self):
        self.state = "open"

    def close(self):
        self.state = "closed"


# PLC Logic to Manage Tank
class PLCLogic:
    def __init__(self, water_sensor, temp_sensor, inlet_valve, outlet_valve, heater, min_level, max_level, target_temp):
        self.water_sensor = water_sensor
        self.temp_sensor = temp_sensor
        self.inlet_valve = inlet_valve
        self.outlet_valve = outlet_valve
        self.heater = heater
        self.min_level = min_level
        self.max_level = max_level
        self.target_temp = target_temp

    def process(self):
        # Inlet valve control
        current_level = self.water_sensor.measure()
        if current_level <= self.min_level:
            self.inlet_valve.open()
        elif current_level >= self.max_level:
            self.inlet_valve.close()

        # Temperature Control
        current_temp = self.temp_sensor.measure()
        if current_temp < self.target_temp and \
            self.inlet_valve.state == 'closed' and \
            self.outlet_valve.state == 'closed':
            # heat when below target temperature and both valves are closed
            self.heater.turn_on()
        else:
            self.heater.turn_off()

        # Outlet valve control
        if current_temp >= self.target_temp:
            self.outlet_valve.open()
        if current_level <= self.min_level:
            self.outlet_valve.close()

        self.__simulate_physics_step()
    

    def __simulate_physics_step(self):
        if self.inlet_valve.state == "open":
            delta_level = random.uniform(0.2, 0.3)
            self.water_sensor.update_level(delta_level)  # inlet valve increases water level
            
            delta_temperature = -random.uniform(0.1, 0.2)
            self.temp_sensor.update_temperature(delta_temperature) # inlet valve adds cool water

        if self.outlet_valve.state == "open":
            self.water_sensor.update_level(-random.uniform(0.2, 0.3))  # outlet valve drains water
        
        if self.heater.state == "on":
            delta_temperature = random.uniform(0.7, 1.0)
            self.temp_sensor.update_temperature(delta_temperature)  # Heater warms water
        else:
            delta_temperature = -random.uniform(0.04, 0.05)
            self.temp_sensor.update_temperature(delta_temperature)  # Water slowly cools if not heated


# Main Simulation Loop
def simulation_loop():
    # Initialize components
    water_sensor = WaterLevelSensor(sensor_id="water_level_sensor_01", initial_level=0.0)
    temp_sensor = WaterTemperatureSensor(sensor_id="water_temp_sensor_01", initial_temp=25.0)
    inlet_valve = ValveActuator(actuator_id="inlet_valve_01", initial_state="closed")
    outlet_valve = ValveActuator(actuator_id="outlet_valve_01", initial_state="closed")
    heater = HeaterActuator(actuator_id="heater_actuator_01", initial_state="off")

    plc = PLCLogic(
        water_sensor,
        temp_sensor,
        inlet_valve,
        outlet_valve,
        heater,
        min_level=30.0,
        max_level=70.0,
        target_temp=80.0,
    )
    
    # Simulation loop
    while True:
        site = "site1"

        # Update PLC logic
        plc.process()

        # Store in InfluxDB (line protocol)
        influx_data = f"boiler,sensor_id={water_sensor.sensor_id},site={site} water_level={water_sensor.measure()}\n"
        influx_data += f"boiler,sensor_id={temp_sensor.sensor_id},site={site} water_temperature={temp_sensor.measure()}\n"
        influx_data += f"boiler,actuator_id={inlet_valve.actuator_id},site={site} inlet_valve_state={1 if inlet_valve.state == 'open' else 0 }\n"
        influx_data += f"boiler,actuator_id={outlet_valve.actuator_id},site={site} outlet_valve_state={1 if outlet_valve.state == 'open' else 0 }\n"
        influx_data += f"boiler,actuator_id={heater.actuator_id},site={site} heater_state={1 if heater.state == 'on' else 0 }\n"

        # Here you would send influx_data to InfluxDB using HTTP API
        connection = None
        try:
            connection = http.client.HTTPConnection(INFLUXDB_HOST, INFLUXDB_PORT, timeout=5)
            connection.request("POST", f"/api/v2/write?org={INFLUXDB_ORG}&bucket={INFLUXDB_BUCKET}", influx_data, {"Content-Type": "text/plain", "Authorization": f"Token {INFLUXDB_TOKEN}"})
            response = connection.getresponse()
            response.read()  # drain response to allow connection reuse
            if response.status >= 300:
                print(f"InfluxDB write failed: {response.status} {response.reason}")
        except Exception as exc:
            print(f"Error writing to InfluxDB: {exc}")
        finally:
            try:
                if connection:
                    connection.close()
            except Exception:
                pass


        # Wait 1 second
        time.sleep(1)

if __name__ == "__main__":
    simulation_loop()