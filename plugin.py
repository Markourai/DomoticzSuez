#           Suez Plugin (toutsurmoneau)
#
#           Authors:
#           Copyright (C) 2018 Markourai
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""
<plugin key="suez" name="Suez" author="Markourai" version="1.0.5" externallink="https://github.com/Markourai/DomoticzSuez">
    <params>
        <param field="Username" label="Username" width="200px" required="true" default=""/>
        <param field="Password" label="Password" width="200px" required="true" default="" password="true"/>
        <param field="Mode6" label="Counter ID" width="200px" required="true" default="" />
        <param field="Mode1" label="Number of days to grab for daily view (30 min, 1000 max)" width="50px" required="false" default="365"/>
        <param field="Mode3" label="Debug" width="75px">
            <options>
                <option label="False" value="0"  default="true" />
                <option label="True" value="1"/>
                <option label="Advanced" value="2"/>
                
            </options>
        </param>
    </params>
</plugin>
"""
# https://www.domoticz.com/wiki/Developing_a_Python_plugin
try:
    import Domoticz
except ImportError:
    import fakeDomoticz as Domoticz
from base64 import b64encode
import json
from urllib.parse import quote
import re
from datetime import datetime
from datetime import timedelta
import time
import html

LOGIN_BASE_URI = 'www.toutsurmoneau.fr'
API_BASE_URI = 'www.toutsurmoneau.fr'
BASE_PORT = '443'

API_ENDPOINT_LOGIN = '/mon-compte-en-ligne/je-me-connecte'
API_ENDPOINT_DATA = '/mon-compte-en-ligne/statJData'

HEADERS = {
    "Accept" : "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept-Language" : "fr,fr-FR;q=0.8,en;q=0.6",
    "User-Agent" : "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Mobile Safari/537.36",
    "Connection": "keep-alive",
}

class BasePlugin:
    # int: debug mode
    iDebugLevel = None
    # boolean: to check that we are started, to prevent error messages when disabling or restarting the plugin
    isStarted = None
    # object: http connection
    httpConn = None
    # integer: index of the Suez device
    iIndexUnit = 1
    # string: name of the Suez device
    sDeviceName = "Suez"
    # string: description of the Suez device
    sDescription = "Compteur Suez"
    # integer: type (pTypeGeneral)
    iType = 0xF3
    # integer: subtype (sTypeManagedCounter)
    iSubType = 0x21
    # integer: switch type (Water m3)
    iSwitchType = 2
    # string: step name of the state machine
    sConnectionStep = None
    # boolean: true if a step failed
    bHasAFail = None
    # dict: cookies
    dCookies = None
    # string: website token
    sToken = None
    # string: counter ID for history
    sCounter = None
    # string: current year for history
    sYear = None
    # string: current month for history
    sMonth = None
    # date : current date for history
    dateCurrentData = None
    # string: end year for history
    sEndYear = None
    # string: end month for history
    sEndMonth = None
    # integer: number of days of data to grab for history
    iHistoryDaysForDaysView = None
    # integer: number of days left for next batch of data
    iDaysLeft = None
    # boolean: is this the batch of the most recent history
    bFirstMonths = None
    # string: username for Suez website
    sUser = None
    # string: password for Suez website
    sPassword = None
    # string: consumption to show = current week ("week"), the previous week ("lweek", the current month ("month"), the previous month ("lmonth"), or year ("year")

    def __init__(self):
        self.isStarted = False
        self.httpConn = None
        self.sConnectionStep = "idle"
        self.bHasAFail = False
        self.iDaysLeft = False

    def myDebug(self, message):
        if self.iDebugLevel:
            Domoticz.Log(message)

    # Reset saved cookies
    def resetCookies(self):
        self.dCookies = {}

    # Grab cookies found in Data["Headers"] and saves them for later user
    def getCookies(self, Data):
        if Data and ("Headers" in Data) and ("Set-Cookie" in Data["Headers"]):
            for match in re.finditer("^(.*?)=(.*?)[;$]", Data["Headers"]["Set-Cookie"], re.MULTILINE):
                self.dCookies[match.group(1)] = match.group(2)
                self.myDebug(match.group(1) + " : " + match.group(2))

    # Write saved cookies in headers["Cookie"]
    def setCookies(self, headers):
        headers["Cookie"] = ""
        for sKey, sValue in self.dCookies.items():
            # Concatenate cookies
            if headers["Cookie"]:
                headers["Cookie"] += "; "
            headers["Cookie"] += sKey + "=" + sValue

    # Store token needed for website
    def setToken(self, Data):
        strData = ""
        if Data and ("Data" in Data):
            strData = Data["Data"].decode();
            regex=re.compile('"_csrf_token" value="(.*)"',re.I) #re.I permet d'ignorer la case (majuscule/minuscule)
            match=regex.search(strData)
            if match:
                self.myDebug(match.group(1))
                self.sToken = match.group(1)

    # get default headers
    def initHeaders(self):
        return dict(HEADERS)

    # get website token (Suez toutsurmoneau) through http connection
    def getToken(self):

        headers = self.initHeaders()
        headers["Host"] = LOGIN_BASE_URI + ":" + BASE_PORT

        sendData = {
                    "Verb" : "GET",
                    "URL"  : API_ENDPOINT_LOGIN,
                    "Headers" : headers
        }
        # Reset cookies to get authentication cookie later
        self.resetCookies()
        # Send data
        self.httpConn.Send(sendData)

    # send login details through http connection
    def login(self, username, password):
        payload = {
            '_username': username,
            '_password': password,
            '_csrf_token': self.sToken,
            'signin[username]': username,
            'signin[password]' : None,
            'tsme_user_login[_username]': username,
            'tsme_user_login[_password]': password
        }

        headers = self.initHeaders()
        headers["Host"] = LOGIN_BASE_URI + ":" + BASE_PORT
        self.setCookies(headers)

        sendData = {
                    "Verb" : "POST",
                    "URL"  : API_ENDPOINT_LOGIN,
                    "Headers" : headers,
                    "Data" : dictToQuotedString(payload)
        }

        self.dumpDictToLog(sendData)
        # Reset cookies to get authentication cookie later
        self.resetCookies()
        # Send data
        self.httpConn.Send(sendData)

    # ask data to toutsurmoneau website, based on a counter_id ("counter number") and date of current month (year and month)
    def getData(self, counter_id, year_date, month_date):
        headers = self.initHeaders()
        headers["Host"] = API_BASE_URI + ":" + BASE_PORT

        #Copy cookies
        self.setCookies(headers)
        self.dumpDictToLog(headers)

        sendData = {
                    "Verb" : "GET",
                    "URL"  : API_ENDPOINT_DATA + "/" + year_date + "/" + month_date + "/" + counter_id,
                    "Headers" : headers
        }
        #self.dumpDictToLog(sendData)
        self.httpConn.Send(sendData)

    # Create Domoticz device
    def createDevice(self):
        # Only if not already done
        if not self.iIndexUnit in Devices:
            Domoticz.Device(Name=self.sDeviceName,  Unit=self.iIndexUnit, Type=self.iType, Subtype=self.iSubType, Switchtype=self.iSwitchType, Description=self.sDescription, Used=1).Create()
            if not (self.iIndexUnit in Devices):
                Domoticz.Error("Cannot add Suez device to database. Check in settings that Domoticz is set up to accept new devices")
                return False
        return True

    # Create device and insert usage in Domoticz DB
    def createAndAddToDevice(self, usage, usageTotal, Date):
        if not self.createDevice():
            return False

        sNewValue=str(usageTotal) + ";" + str(usage) + ";" + str(Date)
        self.myDebug("Insert this value into the DB: " + sNewValue)
        Devices[self.iIndexUnit].Update(nValue=0, sValue=sNewValue, Type=self.iType, Subtype=self.iSubType, Switchtype=self.iSwitchType,)
        return True

    # Update value shown on Domoticz dashboard
    def updateDevice(self, usage, usageTotal):
        if not self.createDevice():
            return False

        sUpdateValue=str(usageTotal) + ";"+ str(usage)
        self.myDebug("Update dashboard with this value: " + sUpdateValue)
        Devices[self.iIndexUnit].Update(nValue=0, sValue=sUpdateValue, Type=self.iType, Subtype=self.iSubType, Switchtype=self.iSwitchType)
        return True

    # Show error in state machine context
    def showStepError(self, days, logMessage):
        if days:
            Domoticz.Error(logMessage + " during step " + self.sConnectionStep + " for days of year " + self.sYear + " and month " + self.sMonth)
        else:
            Domoticz.Error(logMessage + " during step " + self.sConnectionStep + " for months of year " + self.sYear)

    # Grab days data inside received JSON data for history
    def exploreDataDays(self, Data):
        self.myDebug("Begin Data Days")
        curDay = None
        curIndexDay = None
        curTotalIndexDay = None
        self.dumpDictToLog(Data)

        if Data and "Data" in Data:
            try:
                dJson = json.loads(Data["Data"].decode())
                dJson.reverse()
            except ValueError as err:
                self.showStepError(True, "Data received are not JSON: " + str(err))
                return False
            except TypeError as err:
                self.showStepError(True, "Data type received is not JSON: " + str(err))
                return False
            except:
                self.showStepError(True, "Error in JSON data: " + sys.exc_info()[0])
                return False
            else:
                for day in range(len(dJson)):
                    for i, value in enumerate(dJson[day]):
                        if i == 0:
                            try:
                                curDay = suezDateToDatetime(value)
                            except ValueError as err:
                                self.showStepError(True, "Error in received JSON data time format: " + str(err))
                                return False
                            except:
                                self.showStepError(True, "Error in received JSON data time: " + sys.exc_info()[0])
                                return False
                        if i == 1:
                            # Convert m3 consumption to liter (DON'T FORGET TO SET DEVICE LIMITER TO 1000)
                            curIndexDay = float(value) * 1000.0
                        if i == 2:
                            curTotalIndexDay = float(value) * 1000.0
                    # Update only if there is a value
                    if (curIndexDay > 0.0):
                        #Domoticz.Log("Value " + str(curIndexDay) + " with total of " + str(curTotalIndexDay) + " for " + datetimeToSQLDateString(curDay))
                        if not self.createAndAddToDevice(curIndexDay, curTotalIndexDay, datetimeToSQLDateString(curDay)):
                            return False
                        # If we are on the most recent batch and end date, use the most recent data for Domoticz dashboard
                        if self.bFirstMonths:
                            self.bFirstMonths = False
                            if not self.updateDevice(curIndexDay, curTotalIndexDay):
                                return False
                        else:
                            if self.iDaysLeft > 0:
                                self.iDaysLeft = self.iDaysLeft - 1
                return True
            #else:
                #self.showStepError(True, "Error in received JSON data")
        else:
            self.showStepError(True, "Didn't received data")
        return False

    # Calculate year and month for data pulling
    def calculateMonthData(self):
        self.myDebug("Number of days left: "+ str(self.iDaysLeft))
        # Remove one day to get correct data and avoid month change issue
        self.dateCurrentData = (datetime.now() - timedelta(days=self.iDaysLeft) - timedelta(days=1))
        self.myDebug(str(self.dateCurrentData))
        bNewData = False
        # Set year and month for data request
        if (self.sYear is None) or (self.sYear != str(self.dateCurrentData.year)):
            self.sYear = str(self.dateCurrentData.year)
            bNewData = True

        if (self.sMonth is None) or (self.sMonth != str(self.dateCurrentData.month)):
            self.sMonth = str(self.dateCurrentData.month)
            bNewData = True

        if (self.sMonth == self.sEndMonth) and (self.sYear == self.sEndYear):
            self.bFirstMonths = True

        if bNewData:
            return

        if (self.sYear == str(self.dateCurrentData.year)) and (self.sMonth == str(self.dateCurrentData.month)):
            self.myDebug("Same year: " + self.sYear + " and month: " + self.sMonth)
            if self.iDaysLeft > 0:
                self.iDaysLeft = self.iDaysLeft - 1
                self.calculateMonthData()


    # Calculate next complete grab, for tomorrow between 8 and 9 am if tomorrow is true, for next hour otherwise
    def setNextConnection(self, tomorrow):
        if tomorrow:
            self.nextConnection = datetime.now() + timedelta(days=1)
            self.nextConnection = self.nextConnection.replace(hour=8)
            if self.iDaysLeft == 0:
                self.iDaysLeft = 1
        else:
            self.nextConnection = datetime.now() + timedelta(hours = 1)
        # Randomize minutes to lower load on toutsurmoneau website
        # We take microseconds to randomize
        minutesRand = round(datetime.now().microsecond / 10000) % 60
        self.nextConnection = self.nextConnection + timedelta(minutes=minutesRand)

    # Handle the connection state machine
    def handleConnection(self, Data = None):
        # First and last step
        self.myDebug(self.sConnectionStep)
        if self.sConnectionStep == "idle":
            self.myDebug("Starting connection...")
            # Reset failed state
            self.bHasAFail = False
            if self.httpConn and self.httpConn.Connected():
                self.httpConn.Disconnect()

            self.httpConn = Domoticz.Connection(Name="HTTPS connection", Transport="TCP/IP", Protocol="HTTPS", Address=LOGIN_BASE_URI, Port=BASE_PORT)
            self.sConnectionStep = "connecting"
            self.httpConn.Connect()

        # We need to retrieve token
        elif self.sConnectionStep == "connecting":
            if not self.httpConn.Connected():
                Domoticz.Error("Connection failed for token")
                self.sConnectionStep = "idle"
                self.bHasAFail = True
            else:
                self.myDebug("Getting token...")
                self.sConnectionStep = "tokenconnected"
                self.getToken()

        # Connected, we need to log in
        elif self.sConnectionStep == "tokenconnected":
            if not self.httpConn.Connected():
                Domoticz.Error("Getting token failed")
                self.sConnectionStep = "idle"
                self.bHasAFail = True
            else:
                Domoticz.Log("Starting login...")
                self.setToken(Data)
                self.getCookies(Data)
                self.sConnectionStep = "logconnected"
                self.login(self.sUser, self.sPassword)

        # Connected, check that the authentication cookie has been received
        elif self.sConnectionStep == "logconnected":
            self.dumpDictToLog(Data)
            # Grab cookies from received data, if we have "eZSESSID", we're good
            self.getCookies(Data)
            if ("eZSESSID" in self.dCookies) and self.dCookies["eZSESSID"]:
                # Proceed to data page
                self.sConnectionStep = "dataconnecting"
                self.httpConn = Domoticz.Connection(Name="HTTPS connection", Transport="TCP/IP", Protocol="HTTPS", Address=API_BASE_URI, Port=BASE_PORT)
                self.httpConn.Connect()
            else:
                Domoticz.Error("Login failed, will try again later")
                self.sConnectionStep = "idle"
                self.bHasAFail = True

        # If we are connected, we must have the authentication cookie then we ask for daily data
        elif self.sConnectionStep == "dataconnecting":
            if not self.httpConn.Connected():
                Domoticz.Error("Login failed with cookies, will try again later")
                self.sConnectionStep = "idle"
                self.bHasAFail = True
            else:
                Domoticz.Log("Getting data for year: " + self.sYear + " and month: " + self.sMonth)
                self.getCookies(Data)
                self.sConnectionStep = "getdatadays"
                # Get data for specific year and month
                self.getData(self.sCounter, self.sYear, self.sMonth)

        # We should have received data and we will parse them
        elif self.sConnectionStep == "getdatadays":
            if not self.httpConn.Connected():
                Domoticz.Error("Connection failed for data")
                self.sConnectionStep = "idle"
                self.bHasAFail = True
            else:
                Domoticz.Log("Parsing data for year: " + self.sYear + " and month: " + self.sMonth)
                self.getCookies(Data)
                self.dumpDictToLog(Data)
                if not self.exploreDataDays(Data):
                    self.bHasAFail = True
                    self.sConnectionStep = "idle"
                else:
                    Domoticz.Log("Got data for year: " + self.sYear + " and month: " + self.sMonth)
                    if self.iDaysLeft > 0:
                        #self.bFirstMonths = False
                        self.nextConnection = datetime.now()
                        self.sConnectionStep = "logconnected"
                    # We have parsed everything
                    else:
                        self.sConnectionStep = "idle"
                        Domoticz.Log("Done")

        # Next connection time depends on success
        if self.sConnectionStep == "idle":
            if self.bHasAFail:
                self.setNextConnection(False)
            Domoticz.Log("Next connection: " + datetimeToSQLDateTimeString(self.nextConnection))

    def onStart(self):
        Domoticz.Heartbeat(20)
        self.myDebug("onStart called")
        
        self.sUser = Parameters["Username"]
        self.sPassword = Parameters["Password"]
        try:
            self.sCounter = Parameters["Mode6"]
        except:
            self.sConnectionStep = "idle"
            self.bHasAFail = True
        # History for short log is 1000 days max (default to 365)
        try:
            self.iHistoryDaysForDaysView = int(Parameters["Mode1"])
        except:
            self.iHistoryDaysForDaysView = 365
        if self.iHistoryDaysForDaysView < 30:
            self.iHistoryDaysForDaysView = 30
        elif self.iHistoryDaysForDaysView > 1000:
            self.iHistoryDaysForDaysView = 1000

        # enable debug if required
        try:
            self.iDebugLevel = int(Parameters["Mode3"])
        except ValueError:
            self.iDebugLevel = 0

        if self.iDebugLevel > 1:
            Domoticz.Debugging(1)

        Domoticz.Log("Username set to " + self.sUser)
        Domoticz.Log("Counter ID set to " + self.sCounter)
        if Parameters["Password"]:
            Domoticz.Log("Password is set")
        else:
            Domoticz.Log("Password is not set")
        Domoticz.Log("Days to grab for daily view set to " + str(self.iHistoryDaysForDaysView))
        Domoticz.Log("Debug set to " + str(self.iDebugLevel))

        # most init
        self.__init__()

        if self.createDevice():
            self.nextConnection = datetime.now()
        else:
            self.setNextConnection(False)

        self.sEndYear = str(datetime.now().year)
        self.sEndMonth = str(datetime.now().month)
        self.iDaysLeft = self.iHistoryDaysForDaysView

        # Now we can enabling the plugin
        self.isStarted = True

    def onStop(self):
        Domoticz.Debug("onStop called")
        # prevent error messages during disabling plugin
        self.isStarted = False

    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug("onConnect called")
        if self.isStarted and (Connection == self.httpConn):
            self.handleConnection()

    def onMessage(self, Connection, Data):
        Domoticz.Debug("onMessage called")

        # if started and not stopping
        if self.isStarted and (Connection == self.httpConn):
            self.handleConnection(Data)

    def onDisconnect(self, Connection):
        Domoticz.Debug("onDisconnect called")

    def onHeartbeat(self):
        Domoticz.Debug("onHeartbeat() called")
        if datetime.now() > self.nextConnection:
            # We immediatly program next connection for tomorrow, if there is a problem, we will reprogram it sooner
            self.setNextConnection(True)
            self.calculateMonthData()
            self.handleConnection()

    def dumpDictToLog(self, dictToLog):
        if self.iDebugLevel > 1:
            if isinstance(dictToLog, dict):
                self.myDebug("Dict details ("+str(len(dictToLog))+"):")
                for x in dictToLog:
                    if isinstance(dictToLog[x], dict):
                        self.myDebug("--->'"+x+" ("+str(len(dictToLog[x]))+"):")
                        for y in dictToLog[x]:
                            if isinstance(dictToLog[x][y], dict):
                                for z in dictToLog[x][y]:
                                    self.myDebug("----------->'" + z + "':'" + str(dictToLog[x][y][z]) + "'")
                            else:
                                self.myDebug("------->'" + y + "':'" + str(dictToLog[x][y]) + "'")
                    else:
                        self.myDebug("--->'" + x + "':'" + str(dictToLog[x]) + "'")
            else:
                self.myDebug("Received no dict: " + str(dictToLog))

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onDeviceAdded(Unit):
    global _plugin

def onDeviceModified(Unit):
    global _plugin

def onDeviceRemoved(Unit):
    global _plugin

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

# Generic helper functions
def dictToQuotedString(dParams):
    result = ""
    for sKey, sValue in dParams.items():
        if result:
            result += "&"
        if sValue != None:
            result += sKey + "=" + quote(str(sValue))
        else:
            result += sKey
    return result

def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            self.myDebug( "'" + x + "':'" + str(Parameters[x]) + "'")
    self.myDebug("Device count: " + str(len(Devices)))
    for x in Devices:
        self.myDebug("Device:           " + str(x) + " - " + str(Devices[x]))
        self.myDebug("Device ID:       '" + str(Devices[x].ID) + "'")
        self.myDebug("Device Name:     '" + Devices[x].Name + "'")
        self.myDebug("Device iValue:    " + str(Devices[x].iValue))
        self.myDebug("Device sValue:   '" + Devices[x].sValue + "'")
        self.myDebug("Device LastLevel: " + str(Devices[x].LastLevel))
    return

# Convert Suez date string to datetime object
def suezDateToDatetime(datetimeStr):
    return datetime(*(time.strptime(datetimeStr, "%d/%m/%Y")[0:6]))

# Convert datetime object to Domoticz date string
def datetimeToSQLDateString(datetimeObj):
    return datetimeObj.strftime("%Y-%m-%d")

# Convert datetime object to Domoticz date and time string
def datetimeToSQLDateTimeString(datetimeObj):
    return datetimeObj.strftime("%Y-%m-%d %H:%M:%S")
