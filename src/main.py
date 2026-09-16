# - Import libraries
import board
import pwmio
import time
import analogio
import digitalio
import busio
import sdcardio
import storage
import os

# Function that converts analogue counts to the equivalent voltage
def countsToVolts(counts, V_max, V_min):
    # Converts Counts to Voltage value
    voltage = (counts / ((2**bitDepth) - 1)) * (V_max - V_min) + V_min
    return voltage

# Function tat converts equivalent voltage to desired measurement
def voltageToMeasurement(SensorVoltage, SensorV_max, SensorV_min, Sensor_max, Sensor_min):
    # Converts Voltage to Measurement value
    measurement = (SensorVoltage - SensorV_min) * ((Sensor_max - Sensor_min) / (SensorV_max - SensorV_min)) + Sensor_min
    return measurement

# Function that retrieves the sensed voltage, V
def motorVoltage(voltAnalog):
    # Measures Voltage
    SensorCounts = voltAnalog.value
    V_max = 2.91
    V_min = 0.2
    Sensor_min = 1.79
    Sensor_max = 24.9
    SensorVoltage = countsToVolts(SensorCounts, V_max, V_min)
    SV_max = 2.91
    SV_min = 0.2

    measurement = voltageToMeasurement(SensorVoltage, SV_max, SV_min, Sensor_max, Sensor_min)
    motorVoltage = measurement

    return motorVoltage

# Function that retrieves the sensed current, A
def motorCurrent(currentAnalog):
    # Measures Current
    I_min = 0
    I_max = 40
    V_max = 3.3
    V_min = 0

    sensorCounts = currentAnalog.value
    V_bias = 1.62
    currentSensitivity = 25  # A/v

    sensorVoltage = countsToVolts(sensorCounts, V_max, V_min)
    SV_max = (I_max / currentSensitivity) + V_bias
    SV_min = (I_min / currentSensitivity) + V_bias

    #current = (SensorVoltage - V_bias) * currentSensitivity
    current = voltageToMeasurement(sensorVoltage, SV_max, SV_min, I_max, I_min)
    return abs(current)

# Function that retrives the sensed RPM
def motorRPM(RPMAnalog):
    # Measures RPM

    RPM_min = 0
    RPM_max = 12000
    V_max = 5
    V_min = 0
    V_bias = 0

    SensorCounts = RPMAnalog.value
    RPMSensitivity = 3636

    SensorVoltage = countsToVolts(SensorCounts, V_max, V_min)
    SV_max = (RPM_max / RPMSensitivity) + V_bias
    SV_min = (RPM_min / RPMSensitivity) + V_bias

    RPM = voltageToMeasurement(SensorVoltage, SV_max, SV_min, RPM_max, RPM_min)

    return RPM

# Function that retrives data from load cell
def LoadCellOutput(loadCellUART):
    # Will attempt to decode and retrieve data
    try:
        data = loadCellUART.readline()
        rxString = data.decode("ascii")
        frame, rxThrust, rxTorque = rxString.split(", ") # Splits data into 3 parts
        thrust = float(rxThrust)
        torque = float(rxTorque.split(">")[0]) # needs to split of the > due to nature of serial message

        desiredData = [thrust, torque]
        return desiredData
    # If error occurs [0, 0] is returned
    except Exception as e:
        #print(e)
        return [0, 0]

# Retrieves thrust from the data
def motorThrust(desiredData):
    # Retrieves current Thrust
    thrust = desiredData[0]
    return thrust

# Retrieves torque from the data
def motorTorque(desiredData):
    # Retrieves current Torque
    torque = desiredData[1]
    return torque

# Calculates the Pulse Width from the inputted throttle
def calcPulseWidth(throttle):
    # Calculates current Pulse Width
    pwMin = 1000  # microseconds
    pwMax = 2000  # microseconds
    throttleMin = 0
    throttleMax = 100
    pulseWidth = ((throttle - throttleMin) * ((pwMax - pwMin) / (throttleMax - throttleMin))) + pwMin

    return pulseWidth

# Calculates duty cycle from the Pulse Width
def calcDuty(pulseWidth, motorSignal):
    # Calculates Duty for ESC
    duty = (pulseWidth / 1000000) * motorSignal * ((2 ** bitDepth) - 1)
    return duty

# - Task 2d - Function to calculate average over period
def average(values):
    numValues = len(values)
    total = sum(values)
    average = total / numValues

    return average

# Used to determine the current most recent file number
def findFileNum(directory):
    # Files sorted based on key, sorts based on number in file name.
    files = os.listdir(directory)
    files.sort(key=lambda file : int(file.split("-")[-1].split(".csv")[0]))

    for file in files:
        # Looks through each file to find the most recent version and increments
        if file.startswith("DAS"):
            fileSplit = file.split("-")[-1]
            fileNumber = fileSplit.split(".csv")[0]
            fileNumber = int(fileNumber) + 1
        else:
            pass

    return fileNumber

if __name__ == "__main__":
    # - Initialise Pin connections
    voltAnalog = analogio.AnalogIn(board.A1)
    currentAnalog = analogio.AnalogIn(board.A2)
    RPMAnalog = analogio.AnalogIn(board.A0)
    loadCellUART = busio.UART(board.GP12, board.GP13, baudrate=9600, timeout=0.05)  # timeout ensures that a full frame is always received

     # - Initialise LED for visual indication of pause during airspeed change
    pauseLed = digitalio.DigitalInOut(board.GP5)
    pauseLed.direction = digitalio.Direction.OUTPUT

    # - Initialse button to allow resuming after airspeed change
    airspeedChange = digitalio.DigitalInOut(board.GP22)
    airspeedChange.switch_to_input(pull=digitalio.Pull.DOWN)

    # - Initialise button for Emergency Stop
    emergencyStop = digitalio.DigitalInOut(board.GP15)
    emergencyStop.switch_to_input(pull=digitalio.Pull.DOWN)

    # - Initialse buzzer for voltage and current warning
    warningBuzzer = pwmio.PWMOut(board.GP7, variable_frequency=True)
    buzzerDuty = 32768
    voltageWarning = 2000
    currentWarning = 500

    # - Initialise Constants and timers
    sampleNum = 0
    bitDepth = 16
    motorSignal = 50  # Hz
    measurementTimer = time.monotonic()
    measurementUpdate = 1
    stallTime = 2

    throttleSampleTimer = time.monotonic()
    throttleSampleTime = 10

    averageTimer = time.monotonic()
    averageWait = 5

    # - Initialse the PWM signal for the Electronic Speed Controller
    ESCInput = pwmio.PWMOut(board.GP20, frequency=motorSignal)
    ESCInput.duty_cycle = 0 # Sets the throttle to low before testing begins

    # - Initialising Measurement Variables
    i = 0
    thrust = [0, 0, 0, 0, 0]
    torque = [0, 0, 0, 0, 0]
    RPM = [0, 0, 0, 0, 0]
    current = [0, 0, 0, 0, 0]
    voltage = [0, 0, 0, 0, 0]
    airspeed = [8,10,12]
    duty = 1

    highCurrentTime = 10
    throttle = [10, 20, 30, 40, 50, 60, 70, 80]
    sampling = False
    highCurrent = time.monotonic() + 1000
    currentThreshold = False

    directory = "/sd"

     # - Initialisation of SD card
    spi = busio.SPI(clock=board.GP18, MOSI=board.GP19, MISO=board.GP16)
    cs = board.GP17
    sdcard = sdcardio.SDCard(spi, cs)
    vfs = storage.VfsFat(sdcard)
    storage.mount(vfs, directory)

    # - Retrieve file number, if no file exists then start at 0
    fileNumber = 0
    fileNumber = findFileNum(directory)

    # - Opens a new file with an incremented file name
    with open(f"{directory}/DAS-{fileNumber}.csv", "w") as file:
        # - Creates file with desired headers
        file.write("Sample Number - Windspeed (ms-1) - ESC Throttle Setting (Hz) - Average Current (A) - Average Voltage (V) - Average RPM (RPM) - Average Force (N) - Average Torque (Nm) \r\n")

    # - Loop will not run if throttle is 0 or sampling has finished
    while throttle != 0 and not sampling:
        for k in range(0,3): # Index indicator for the airspeed array
            # Pauses the sampling to allow airspeed change
            while not airspeedChange.value and throttle != 0:
                pauseLed.value = True
            # Check for Emergency Stop
            if throttle == 0:
                break

            # LED turns off to indicate testing can resume
            pauseLed.value = False
            for j in range(0, len(throttle)): # index indicator for throttle array
                print("\nPausing due to Invalid Data\n")

                if throttle == 0:
                    break

                # Creation of PWM motor signal
                pulseWidth = calcPulseWidth(throttle[j])
                duty = int(calcDuty(pulseWidth, motorSignal))
                ESCInput.duty_cycle = duty # Changes RPM using calculated duty

                # Pauses testing for 2 seconds to allow throttle change to take place
                stallTimer = time.monotonic()
                while time.monotonic() < (stallTimer + stallTime):
                    # For each throttle values are reset
                    RPM = [0, 0, 0, 0, 0]
                    current = [0, 0, 0, 0, 0]
                    voltage = [0, 0, 0, 0, 0]
                    thrust = [0, 0, 0, 0, 0]
                    torque = [0, 0, 0, 0, 0]

                # Start sampling and average timers
                throttleSampleTimer = time.monotonic()
                averageTimer = time.monotonic()

                # 10 seconds of sampling for each throttle setting
                while time.monotonic() < (throttleSampleTimer + throttleSampleTime) and throttle != 0:

                    if emergencyStop.value: # Check for emergency stop
                        throttle = 0
                        break

                    # Samples each second
                    if time.monotonic() > (measurementTimer + measurementUpdate):

                        # Retrieves Sensor Data and calculates current measurement variables
                        measurementTimer = time.monotonic()

                        # Sets thrust to zero to force into loop
                        thrust[i] = 0
                        torque[i] = 0
                        # Loop will keep attempting to retrieve UART message until valid message is retrieved
                        #while thrust[i] == 0 or torque[i] == 0:
                        desiredData = LoadCellOutput(loadCellUART)
                        thrust[i] = motorThrust(desiredData)
                        torque[i] = motorTorque(desiredData)

                        if emergencyStop.value: # Emergency Stop check
                            throttle = 0
                            break

                        # Retrieval of values from sensor
                        RPM[i] = motorRPM(RPMAnalog)
                        current[i] = motorCurrent(currentAnalog)
                        voltage[i] = motorVoltage(voltAnalog)
                        power = current[i] * voltage[i]
                        desiredAirspeed = airspeed[k]

                        if emergencyStop.value: # Emergency Stop check
                            throttle = 0
                            break

                        # Buzzer checks to determine if buzzer should warn the user
                        if voltage[i] > 22 and current[i] < 20:
                            warningBuzzer.duty_cycle = 0
                            highCurrent = time.monotonic() + 10
                            currentThreshold = False

                        elif voltage[i] < 22:
                            warningBuzzer.duty_cycle = voltageWarning

                        elif current[i] > 20 and not currentThreshold:
                            highCurrent = time.monotonic()
                            currentThreshold = True

                        elif current[i] < 20:
                            currentThreshold = False
                            highCurrent = time.monotonic() + 10


                        if time.monotonic() > (highCurrent + highCurrentTime):
                            warningBuzzer.duty_cycle = buzzerDuty
                            warningBuzzer.frequency = currentWarning
                        else:
                            warningBuzzer.duty_cycle = 0

                        # After 5 seconds the System begins averaging the collected values
                        if time.monotonic() > (averageTimer + averageWait): # - After 5 seconds averages begin to be made

                            averageCurrent = average(current)
                            averageVoltage = average(voltage)
                            averageRPM = average(RPM)
                            averageThrust = average(thrust)
                            averageTorque = average(torque)

                            # Appends required measurement values to file
                            with open(f"{directory}/DAS-{fileNumber}.csv", "a") as file:
                                sampleNum += 1
                                file.write("%.i,%.i,%.0f,%.1f,%.1f,%.0f,%.3f,%.3f\r\n" % (sampleNum, desiredAirspeed, pulseWidth, averageCurrent, averageVoltage, averageRPM, averageThrust, averageTorque))


                        # - Serial Message
                        print("Current Airspeed:", desiredAirspeed, "m/s", "- Current ESC Throttle:", throttle[j], "%")
                        print("Latest Force:", "%.3f" % thrust[i], "N", "- Latest Torque", "%.3f" % torque[i], "Nm")
                        print("Latest RPM:", "%.i" % RPM[i], "RPM")
                        print("Latest Power:", "%.1f" % power,"W")

                        # Increments i, allowing continuous retrieval of values, overwriting the oldest
                        i += 1
                        if i == 5:
                            i = 0

        sampling = True # Flags once sampling for every setting is complete, breaks the main loop

    # Sets throttle to off and tells the user if the system was stopped due to activation of the Emergency Stop
    ESCInput.duty_cycle = 0
    if throttle == 0:
        print("Emergency Stop Initiated")
    else:
        pass
    # Tells the user the file the data has been saved to
    print(f"Data successfully saved to: {directory}/DAS-{fileNumber}.csv")

# with open(f"{directory}/DAS-{fileNumber}.csv", "r") as file:
#     print(file.read())



