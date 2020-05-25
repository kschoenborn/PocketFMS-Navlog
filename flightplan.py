from xml.dom.minidom import parse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.colors import black, white, lightgrey, red
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Frame
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.textlabels import Label
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.graphics import renderPDF
from os import system
from copy import deepcopy
import math
from math import pi
import calendar

# convert latitude or longitude from floating point to dd.mm.ss format
def ConvertLatLon (latlon,angle,angleformat=0):
 sign = angle/math.fabs(angle)
 if sign == +1 and latlon == "lat": ewns = " N"
 if sign == -1 and latlon == "lat": ewns = " S"
 if sign == +1 and latlon == "lon": ewns = " E"
 if sign == -1 and latlon == "lon": ewns = " W"
 temp=math.modf(math.fabs(angle))
 if angleformat == 0: ConvertLatLon = str(str(format(temp[1],'0>3.0f'))+ ":" + str(format(temp[0]*60,'0>4.1f')) +str(ewns)) # ddd:mm.d
 if angleformat == 1: ConvertLatLon = str(str(format(temp[1],'0>3.0f'))+ ":" + str(format(temp[0]*60,'0>5.2f')) +str(ewns)) # ddd:mm.dd
 if angleformat == 2: ConvertLatLon = str(str(format(temp[1],'0>3.0f'))+ ":" + str(format(temp[0]*60,'0>6.3f')) +str(ewns)) # ddd:mm.ddd
 if angleformat == 3: ConvertLatLon = str(str(format(temp[1],'0>3.0f'))+ ":" + str(format(temp[0]*60,'0>2.0f')) + \
  ":"+ str(format(math.modf(temp[0]*60)[0]*60,'0>2.0f'))+str(ewns)) # ddd:mm:ss
 return ConvertLatLon
 

# calculate sunrise and sunset from departure and destination coordinates
class Sun:
    def __init__(self): 
        self.RADEG = 180.0 / pi ;  self.DEGRAD = pi / 180.0 ;  self.INV360 = 1.0 / 360.0
    def daysSince2000Jan0(self, y, m, d): return (367*(y)-((7*((y)+(((m)+9)/12)))/4)+((275*(m))/9)+(d)-730530)
    def sind(self, x): return math.sin(x * self.DEGRAD)
    def cosd(self, x): return math.cos(x * self.DEGRAD)
    def tand(self, x): return math.tan(x * self.DEGRAD)
    def atand(self, x): return math.atan(x) * self.RADEG
    def asind(self, x): return math.asin(x) * self.RADEG
    def acosd(self, x): return math.acos(x) * self.RADEG
    def atan2d(self, y, x): return math.atan2(y, x) * self.RADEG
    def dayLength(self, year, month, day, lon, lat): return self.__daylen__(year, month, day, lon, lat, -35.0/60.0, 1)
    def sunRiseSet(self, year, month, day, lon, lat): return self.__sunriset__(year, month, day, lon, lat, -35.0/60.0, 1)
    def __sunriset__(self, year, month, day, lon, lat, altit, upper_limb):
        d = self.daysSince2000Jan0(year,month,day) + 0.5 - (lon/360.0)
        sidtime = self.revolution(self.GMST0(d) + 180.0 + lon)
        res = self.sunRADec(d) ; sRA = res[0] ; sdec = res[1] ; sr = res[2]
        tsouth = 12.0 - self.rev180(sidtime - sRA)/15.0;
        sradius = 0.2666 / sr;
        if upper_limb:
            altit = altit - sradius
        cost = (self.sind(altit) - self.sind(lat) * self.sind(sdec))/\
               (self.cosd(lat) * self.cosd(sdec))
        if cost >= 1.0:
            rc = -1
            t = 0.0           # Sun always below altit
        elif cost <= -1.0:
            rc = +1
            t = 12.0;         # Sun always above altit
        else:
            t = self.acosd(cost)/15.0   # The diurnal arc, hours
        return (tsouth-t, tsouth+t)

    def sunpos(self, d):
        M = self.revolution(356.0470 + 0.9856002585 * d)
        w = 282.9404 + 4.70935E-5 * d ; e = 0.016709 - 1.151E-9 * d
        E = M + e * self.RADEG * self.sind(M) * (1.0 + e * self.cosd(M))
        x = self.cosd(E) - e ;  y = math.sqrt(1.0 - e*e) * self.sind(E)
        r = math.sqrt(x*x + y*y)              #Solar distance
        v = self.atan2d(y, x)                 # True anomaly
        lon = v + w                        # True solar longitude
        if lon >= 360.0: lon = lon - 360.0   # Make it 0..360 degrees
        return (lon,r)

    def sunRADec(self, d):
        res = self.sunpos(d) ; lon = res[0]  # True solar longitude
        r = res[1]    # Solar distance
        x = r * self.cosd(lon) ; y = r * self.sind(lon)
        obl_ecl = 23.4393 - 3.563E-7 * d
        z = y * self.sind(obl_ecl) ; y = y * self.cosd(obl_ecl)
        RA = self.atan2d(y, x) ; dec = self.atan2d(z, math.sqrt(x*x + y*y))
        return (RA, dec, r)

    def revolution(self, x): return (x - 360.0 * math.floor(x * self.INV360))
    def rev180(self, x): return (x - 360.0 * math.floor(x * self.INV360 + 0.5))
    def GMST0(self, d): 
        sidtim0 = self.revolution((180.0 + 356.0470 + 282.9404) +
                                     (0.9856002585 + 4.70935E-5) * d)
        return sidtim0;
    
# Flight planning starts here
class calc(object):  # static methods used for calculations
 def addEnrouteTime(takeoff,duration): # calculate the landing time 
  takeoffHours=   int(takeoff[0:2])    # from departure time and
  takeoffMinutes= int(takeoff[2:4])    # enroute time
  durationHours=  int(duration[0:2])
  durationMinutes=int(duration[2:4])
  landingHours=   takeoffHours+durationHours
  landingMinutes= takeoffMinutes+durationMinutes
  if landingHours > 24: landingHours = landingHours - 24
  if landingMinutes >= 60:
   landingMinutes= landingMinutes - 60
   landingHours=   landingHours+1
  if landingHours == 24: landingHours = 0
  return format(landingHours,'1.0f').zfill(2)\
         +format(landingMinutes,'1.0f').zfill(2)
 addEnrouteTime=staticmethod(addEnrouteTime)

 # calculate sunrise and sunset
 def sunRise(dOF,depLat,depLong): 
  k=Sun();sR=k.sunRiseSet(int(dOF[0:4]),int(dOF[5:7]),int(dOF[8:10]),depLong,depLat)[0]
  return str(int(sR)).zfill(2)+format((sR-int(sR))*100*60/100,'1.0f').zfill(2)
 sunRise=staticmethod(sunRise)
 
 def sunSet(dOF,arrLat,arrLong):
  k=Sun();sS=k.sunRiseSet(int(dOF[0:4]),int(dOF[5:7]),int(dOF[8:10]),arrLong,arrLat)[1]
  return str(int(sS)).zfill(2)+format((sS-int(sS))*100*60/100,'1.0f').zfill(2)
 sunSet=staticmethod(sunSet)

# Create a base class for all Flightplanblocks
class FlightplanBlock(object):
 def __init__(self,positionOnPage,blockGrid,blockText,blockData):
  self.pos =  deepcopy([positionOnPage[0]*mm,positionOnPage[1]*mm])
  self.grid = deepcopy(blockGrid)
  self.text = deepcopy(blockText)
  self.data = deepcopy(blockData)
  
 def createBoundary(self):
  self.p.setStrokeColor(black)
  self.p.setLineWidth(0.50*mm)
  self.p.setFillColor(lightgrey)
  for line in self.grid:
   line[0] = [x*mm for x in line[0]] # scale grid to mm
   line[1] = [y*mm for y in line[1]]
   self.p.rect(self.grid[-1][0][0],self.grid[-1][1][ 0],
   self.grid[0][0][-1],self.grid[ 0][1][-1],
   fill=1)

 def createGrid(self):
  self.p.setLineWidth(0.25*mm)
  for line in self.grid: self.p.grid(line[0],line[1])
        
 def drawText(self,text):
  self.p.setFillColor(black)
  for textline in text:
   col=textline[3] ; row=textline[4] ; text=textline[5]
   if textline[1]==0: self.p.setFont("Helvetica",textline[2])
   if textline[1]==1: self.p.setFont("Helvetica-Bold",textline[2])
   if textline[1]==2: # draw a white rectangle without text
    self.p.setFillColor(white)
    self.p.rect(self.grid[row][0][col],self.grid[row][1][0],\
                self.grid[row][0][col+1]-self.grid[row][0][col],\
                self.grid[row][1][1]-self.grid[row][1][0],fill=1)
    self.p.setFillColor(black)
    continue
   if textline[0]==0:
    self.p.drawString(self.grid[row][0][col]+1*mm,\
    (2*self.grid[row][1][0]+ self.grid[row][1][1])/3,text)
   if textline[0]==1:
    self.p.drawCentredString((self.grid[row][0][col]+\
                              self.grid[row][0][col+1])/2,\
    (2*self.grid[row][1][0]+ self.grid[row][1][1])/3,text)
   if textline[0]==2:
    self.p.drawRightString(self.grid[row][0][col+1]-1*mm,\
    (2*self.grid[row][1][0]+ self.grid[row][1][1])/3,text)

 def drawTemplate(self,page):
  self.p = page
  self.p.translate(self.pos[0],self.pos[1]) 
  self.createBoundary()
  self.createGrid()
  self.drawText(self.text)

 def positionReset(self):
  self.p.translate(-self.pos[0],-self.pos[1]) 

class MetarTafBlock(FlightplanBlock):
 def drawFrame(self,text):  
  self.data = text
  x=self.grid[1][0][0]
  y=self.grid[1][1][0]
  width=(self.grid[1][0][1]-self.grid[1][0][0])
  height=(self.grid[1][1][1]-self.grid[1][1][0])
  fmetar=Frame(x,y,width,height,
  showBoundary=0,leftPadding=1*mm,rightPadding=1*mm,
  topPadding=1*mm,bottomPadding=1*mm)
  x=self.grid[1][0][1]
  y=self.grid[1][1][0]
  width=(self.grid[1][0][2]-self.grid[1][0][1])
  height=(self.grid[1][1][1]-self.grid[1][1][0])
  ftaf=  Frame(x,y,width,height,
  showBoundary=0,leftPadding=1*mm,rightPadding=1*mm,
  topPadding=1*mm,bottomPadding=1*mm)
  fmetar.addFromList(self.data[0],self.p)# print out all METARs to Frame fmetar
  ftaf.addFromList(  self.data[1],self.p)# print out all TAFs to Frame ftaf

class DepartureArrivalBlock(FlightplanBlock):
 def __init__(self,positionOnPage,blockGrid,blockText,blockData,remarks):
  self.pos =  deepcopy([positionOnPage[0]*mm,positionOnPage[1]*mm])
  self.grid = deepcopy(blockGrid)
  self.text = deepcopy(blockText)
  self.data = deepcopy(blockData)
  self.remarks = remarks
  
 def drawFrame(self):  
  x=self.grid[-1][0][0]
  y=self.grid[-1][1][0]
  width=(self.grid[-1][0][1]-self.grid[-1][0][0])
  height=(self.grid[-1][1][1]-self.grid[-1][1][0])
  fComment=Frame(x,y,width,height,
  showBoundary=0,leftPadding=6*mm,rightPadding=1*mm,
  topPadding=1*mm,bottomPadding=1*mm)
  fComment.addFromList(self.remarks,self.p)    # print out all Comments to Frame

class WeightAndBalanceBlock(FlightplanBlock):
 def __init__(self,positionOnPage,blockGrid,blockText,blockData,\
              xMin,xMed,xMax,yMin,yMed,yMax):
  self.pos =  deepcopy([positionOnPage[0]*mm,positionOnPage[1]*mm])
  self.grid = deepcopy(blockGrid)
  self.text = deepcopy(blockText)
  self.data = deepcopy(blockData)
  self.xMin = xMin
  self.xMed = xMed
  self.xMax = xMax
  self.yMin = yMin
  self.yMed = yMed
  self.yMax = yMax
  
 def drawChart(self,data):
  wb=Drawing(60*mm,60*mm) # length and width of Drawing space
  lp = LinePlot()
  lp.strokeColor=lightgrey
  lp.fillColor=lightgrey
  lp.x = 7*mm ; lp.width  = 53*mm
  lp.y = 7*mm ; lp.height = 48*mm
  lp.data = data
  lp.joinedLines = 1
  lp.lines[0].strokeColor = black
  lp.lines[0].strokeWidth = 2
  lp.lines[1].strokeColor = red
  lp.lines[1].strokeWidth = 2
  lp.xValueAxis.visibleGrid = 1
  lp.yValueAxis.visibleGrid = 1
  lp.xValueAxis.labels.fontName       = 'Helvetica'
  lp.xValueAxis.labels.fontSize       = 7
  lp.yValueAxis.labels.fontName       = 'Helvetica'
  lp.yValueAxis.labels.fontSize       = 7
  lp.lines[1].symbol = makeMarker('Circle')
  lp.strokeColor = black
  lp.xValueAxis.valueMin = 0.95*self.xMin
  lp.xValueAxis.valueMax = 1.05*self.xMax
  lp.xValueAxis.valueSteps = [self.xMin,round((self.xMin+self.xMed)/2,1),\
  self.xMed,round((self.xMax+self.xMed)/2,1),\
  self.xMax]
  lp.xValueAxis.labelTextFormat = '%2.0f'
  lp.yValueAxis.valueMin = 1.00*self.yMin
  lp.yValueAxis.valueMax = 1.05*self.yMax
  lp.yValueAxis.valueSteps = [self.yMin,round((self.yMin+self.yMed)/2,1),\
  self.yMed,round((self.yMax+self.yMed)/2,1),\
  self.yMax]
  lp.yValueAxis.labelTextFormat = '%2.0f'
  wb.add(lp)
  wb.drawOn(self.p,0,0)

if __name__ == "__main__":
 root = parse("C:\Users\kschoenborn\Documents\PocketFMS\GeneratedFlightDocs\PocketFMSNavLog.xml").documentElement
 meta =       root.getElementsByTagName("META")[0]
 fuel =       root.getElementsByTagName("FUEL")[0]
 supplement = root.getElementsByTagName("SUPPLEMENTARYINFORMATION")[0]
 libs =       root.getElementsByTagName("LIB")    # Leg Information Blocks
 aircraft =   root.getElementsByTagName("AIRCRAFT")[0]  # Aircraft Data
 departure =  meta.getElementsByTagName("Departure")[0] # Departure Aerodrome info
 arrival   =  meta.getElementsByTagName("Arrival")[0]   # Arrival Aerodrome info
 weightAndBalance = aircraft.getElementsByTagName("WeightAndBalance")[0]
 wbMomentLimits =   weightAndBalance.getElementsByTagName("WBMomentLimits")[0]

 # create block 1 with META Flightplan Data
 grid=[[[0, 8,57,66,116,124,141],[15,20]],[[0,27,39,46,57,84,102,121,134,141],[10,15]],#line 1 and 2
 [[0,27,39,46,57,84,102,121,134,141],[ 5,10]],[[0,27,39,46,57,84,102,121,141],[0,5]]]#line 3 and 4
 l=0 ; c=1 ; r=2 # field 0: 0=left,1=centred,2=right
 n=0 ; b=1 ; w=2 # field 1: 0=normal,1=bold, 2=white space
                 # field 2: fontsize
                 # field 3: column starting at 0
                 # field 4: row starting at 0
                 # field 5: Text 
 text=\
 [[c,b,7,0,0,"From"],[r,n,7,0,1,"planned takeoff time:"],[r,n,7,0,2,"planned landing time:"],
  [r,n,7,0,3,"planned enroute time:"],[c,b,7,2,0,"To"],[r,n,7,2,1,"SR:"],
  [r,n,7,2,2,"SS:"],[c,n,7,2,3,"END:"],[c,b,7,4,0,"Date"],[r,n,7,4,1,"actual takeoff time:"],
  [r,n,7,4,2,"actual landing time:"], [r,n,7,4,3,"actual enroute time:"],
  [r,n,7,6,1,"loaded Fuel:"],[r,n,7,6,2,"required Fuel:"],[r,n,7,6,3,"Airplane:"]]
 data=\
 [[c,b,7,1,0,departure.getElementsByTagName("Fullname")[0].firstChild.data.strip()[0:50]],  # departure Fullname
  [c,n,7,1,1,meta.getElementsByTagName("ICAOETD")[0].getAttribute("Value")], # ICAO estimated Time of Departure ETD
  [c,n,7,1,2,calc.addEnrouteTime(meta.getElementsByTagName("ICAOETD")[0].getAttribute("Value"),  # ICAO estimated Time of Landing
             meta.getElementsByTagName("ICAOTOTALEET")[0].getAttribute("Value"))], # not in XML, has to be calculated from ETD and EET
  [c,n,7,1,3,meta.getElementsByTagName("TOTALEET")[0].getAttribute("Value")],  #  estimated Total Enroute Time EET
  [c,b,7,3,0,arrival.getElementsByTagName("Fullname")[0].firstChild.data.strip()[0:50]],  # arrival Fullname
  [c,n,7,3,1,calc.sunRise(meta.getElementsByTagName("TakeOffDateUTC")[0].firstChild.data.strip(), # Calculate Sunrise at Departure
             float(departure.getElementsByTagName("Latitude")[0].firstChild.data.strip()), # this is not in the XML file
             float(departure.getElementsByTagName("Longitude")[0].firstChild.data.strip()))], # so it has to be calculated
  [c,n,7,3,2, calc.sunSet(meta.getElementsByTagName("TakeOffDateUTC")[0].firstChild.data.strip(), # Calculate Sunset at Destination
             float(arrival.getElementsByTagName("Latitude")[0].firstChild.data.strip()), # this is not in the XML file
             float(arrival.getElementsByTagName("Longitude")[0].firstChild.data.strip()))],  # so it has to be calculated
  [c,n,7,3,3,supplement.getElementsByTagName("Endurance")[0].getAttribute("Value")],  # Endurance
  [c,b,7,5,0,meta.getElementsByTagName("TakeOffDateUTC")[0].firstChild.data.strip()], # Date of flight
  [c,w,7,5,1,"white field"], # actual Time of Departure ATD
  [c,w,7,5,2,"white field"], # actual Time of Arrival ATA
  [c,w,7,5,3,"white field"], # actual Time enroute ATE
  [r,n,7,7,1,format(float(fuel.getElementsByTagName("LoadedFuel")[0].getAttribute("Value")),'.1f')],
  [r,n,7,7,2,format(float(fuel.getElementsByTagName("TotalFuel")[0].getAttribute("Value")),'.1f')],
  [l,n,7,8,1,fuel.getElementsByTagName("LoadedFuel")[0].getAttribute("Unit")],
  [l,n,7,8,2,fuel.getElementsByTagName("TotalFuel")[0].getAttribute("Unit")],
  [l,n,7,7,3,aircraft.getElementsByTagName("AircraftDescription")[0].firstChild.data.strip()[0:18]]]
 block1 = FlightplanBlock([5,185],grid,text,data)
 
 # create block 2 with leg information
 grid=[[[0,34,46,66,84,102,121,134,141],[85,90]]]
 for i in range(80,-1,-5):
  grid.append([[0,6,20,34,46,57,66,75,84,93,102,108,115,121,127,134,141],[i,i+5]])
 text=\
 [[c,b,7, 0,0,"Leg Information Block"], [c,b,7, 1,0,"FIS"],
  [c,n,7, 0,1,"No"], [c,n,7, 1,1,"From"],[c,n,7, 2,1,"To"], [c,b,7, 2,0,"Leg Distance"],[c,n,7, 3,1,"COMM"],
  [c,n,7, 4,1,"ACC"],[c,b,7, 3,0,"Leg Time"],[c,n,7, 5,1,"INT"],[c,b,7, 4,0,"T.Overhead"],
  [c,n,7, 6,1,"ACC"],[c,b,7, 5,0,"Heading"],[c,n,7, 7,1,"INT"],[c,b,7, 6,0,"Wind"],
  [c,n,7, 8,1,"EST"],[c,b,7, 7,0,"Fuel"],[c,n,7, 9,1,"ACT"],[c,n,7, 10,1,"MC"],
  [c,n,7,11,1,"WCA"],[c,b,7,12,1,"MH"], [c,n,7,13,1,"DIR"],[c,n,7,14,1,"SP."],
  [c,n,7,15,1,"ACC"]]
 data=[]
 fuelsum = 0.0
 for i,line in enumerate(libs):
  data.append([c,n,7, 0,i+2,line.getAttribute("LibID")])#leg number
  data.append([l,n,7, 1,i+2,str(line.getElementsByTagName("FromPoint")[0].getElementsByTagName("FriendlyShortname")[0].firstChild.data.strip()[0:7])])#from point
  data.append([l,n,7, 2,i+2,str(line.getElementsByTagName("ToPoint")[0].getElementsByTagName("FriendlyShortname")[0].firstChild.data.strip()[0:7])])#to point
  gotfisfreq=0 # set a flag if successfully obtained a FIS freq - not to print it twice in a field
  for aaa in line.getElementsByTagName("FromPoint"): # get the Flight Information Frequency from the Detailed Object Info of the FromPoint
   if aaa.getElementsByTagName("DetailedObjectInfo"): # very nasty procedure because of more than one COMM line
    for bbb in aaa.getElementsByTagName("DetailedObjectInfo"): # Info is sometimes missing in XML, this has to be traced ...
     if bbb.getElementsByTagName("Communications"):
      for ccc in bbb.getElementsByTagName("Communications"):
       if ccc.getElementsByTagName("COMM"):
        for ddd in ccc.getElementsByTagName("COMM"):
         if ddd.getAttribute("CommType") == "FIS" and gotfisfreq == 0:   
          data.append([r,n,7, 3,i+2,ddd.getAttribute("Freq1")])
          gotfisfreq=1
  for aaa in line.getElementsByTagName("ToPoint"): # sometimes the info is bound to the ToPoint, so 
   if aaa.getElementsByTagName("DetailedObjectInfo"): # repeat the procedure once again ...
    for bbb in aaa.getElementsByTagName("DetailedObjectInfo"):
     if bbb.getElementsByTagName("Communications"):
      for ccc in bbb.getElementsByTagName("Communications"):
       if ccc.getElementsByTagName("COMM"):
        for ddd in ccc.getElementsByTagName("COMM"):
         if ddd.getAttribute("CommType") == "FIS" and gotfisfreq == 0:   
          data.append([r,n,7, 3,i+2,ddd.getAttribute("Freq1")])
          gotfisfreq=1
  data.append([r,n,7, 4,i+2,format(float(line.getElementsByTagName("DistanceCummulative")[0].getAttribute("Value")),'.1f')])#acc dist
  data.append([r,n,7, 5,i+2,format(float(line.getElementsByTagName("Distance")[0].getAttribute("Value")),'.1f')])#int dist
  data.append([r,n,7, 6,i+2,line.getElementsByTagName("ETECUMMULATIVE")[0].getAttribute("Value")[0:5]])#acc time
  data.append([r,n,7, 7,i+2,line.getElementsByTagName("ETE")[0].getAttribute("Value")[0:5]])#int time
  data.append([c,w,7, 8,i+2,"white field"])#est time
  data.append([c,w,7, 9,i+2,"white field"])#act time
  data.append([r,n,7,10,i+2,str.zfill(str(line.getElementsByTagName("MAGNETICTRACK")[0].getAttribute("Value")),3)])#mag course
  data.append([r,n,7,11,i+2,str(line.getElementsByTagName("WINDCORRECTIONANGLE")[0].firstChild.data.strip() )])#wca
  data.append([c,b,7,12,i+2,str.zfill(str(line.getElementsByTagName("MAGNETICHEADING")[0].getAttribute("Value")),3)])#mag heading
  data.append([c,n,7,13,i+2,str.zfill(str(line.getElementsByTagName("WINDDIRECTION")[0].getAttribute("Value")),3)])#wind dir
  data.append([r,n,7,14,i+2,str.zfill(str(line.getElementsByTagName("WINDSPEED")[0].getAttribute("Value")),2)])#wind speed
  fuelsum = float(fuelsum) + float( line.getElementsByTagName("FUEL")[0].getAttribute("Value")) # sum up the fuel fields
  data.append([r,n,7,15,i+2,format(fuelsum,'.1f')])# accumulated fuel burn
 block2 = FlightplanBlock([5,95],grid,text,data)

 # create block 3 with waypoint information
 grid=[[[0,34,46,78,110,127,141],[85,90]]]
 for i in range(80,-1,-5):
  grid.append([[0,6,34,46,54,63,71,78,86,95,103,110,120,127,134,141],[i,i+5]])
 text=\
 [[c,b,7, 0,0,"Waypoint Info Block"],
  [c,b,7, 1,0,"Waypoint"],
  [c,n,7, 0,1,"No"],[c,n,7, 1,1,"Name"],[c,n,7, 2,1,"Freq"],[c,n,7, 3,1,"Ident"],
  [c,b,7, 2,0,"Radio Navigation Aid 1"],[c,n,7, 4,1,"Freq"],
  [c,b,7, 3,0,"Radio Navigation Aid 2"],
  [c,n,7, 5,1,"Rad"],[c,b,7, 4,0,"Alternate"],[c,n,7, 6,1,"Dist"],[c,b,7, 5,0,"Altitude"],
  [c,n,7, 7,1,"Ident"],[c,n,7, 8,1,"Freq"],[c,n,7, 9,1,"Rad"],[c,n,7,10,1,"Dist"],
  [c,n,7,11,1,"Name"], [c,n,7,12,1,"Dist"],[c,n,7,13,1,"MSA"],[c,n,7,14,1,"Plan"]]
 data=[]
 for i,line in enumerate(libs):
  data.append([c,n,7, 0,i+2,line.getAttribute("LibID")])#leg number
  data.append([l,n,7, 1,i+2,str.ljust(str(line.getElementsByTagName("ToPoint")[0].\
           getElementsByTagName("FriendlyShortname")[0].firstChild.data.strip()+\
           " - "+line.getElementsByTagName("ToPoint")[0].getElementsByTagName("WaypointType")[0].\
           firstChild.data.strip()),24)[0:20]])#to point
  for aaa in line.getElementsByTagName("ToPoint"): # get Navigation Frequency from the ToPoint
   if aaa.getElementsByTagName("DetailedObjectInfo"): # very nasty procedure because of more than one COMM line
    for bbb in aaa.getElementsByTagName("DetailedObjectInfo"): # Info is sometimes missing in XML, this has to be traced ...
     if bbb.getElementsByTagName("NavaidData"): # if the waypoint is a Radio Beacon, get its Frequncy
      for ccc in bbb.getElementsByTagName("NavaidData"):
       if ccc.getElementsByTagName("NavaidFrequency"):
        data.append([r,n,7, 2,i+2,format(float(ccc.getElementsByTagName("NavaidFrequency")[0].firstChild.data.strip()),'.3f')])
     if bbb.getElementsByTagName("Communications"): # if the waypoint is an Airport, get its Info Frequency if it exists
      for ccc in bbb.getElementsByTagName("Communications"):
       if ccc.getElementsByTagName("COMM"):
        for ddd in ccc.getElementsByTagName("COMM"):
         if ddd.getAttribute("CommType") == "INFO" or "TWR":   
          data.append([r,n,7, 2,i+2,ddd.getAttribute("Freq1")])
          break # print only one frequency if multiple exist
  data.append([r,n,7, 3,i+2,line.getElementsByTagName("ToPoint")[0].getElementsByTagName("RNAV1")[0].getAttribute("BEACONIDENT")])
  data.append([r,n,7, 4,i+2,line.getElementsByTagName("ToPoint")[0].getElementsByTagName("RNAV1")[0].getAttribute("BEACONFREQUENCY")])
  data.append([c,n,7, 5,i+2,str.zfill(format(float(line.getElementsByTagName("ToPoint")[0].\
                getElementsByTagName("RNAV1")[0].getAttribute("BEACONRADIAL")),'.0f'),3)])
  data.append([r,n,7, 6,i+2,format(float(line.getElementsByTagName("ToPoint")[0].\
                getElementsByTagName("RNAV1")[0].getAttribute("BEACONDISTANCENM")),'.1f')])
  data.append([r,n,7, 7,i+2,line.getElementsByTagName("ToPoint")[0].getElementsByTagName("RNAV2")[0].getAttribute("BEACONIDENT")])
  data.append([r,n,7, 8,i+2,line.getElementsByTagName("ToPoint")[0].getElementsByTagName("RNAV2")[0].getAttribute("BEACONFREQUENCY")])
  data.append([c,n,7, 9,i+2,str.zfill(format(float(line.getElementsByTagName("ToPoint")[0].getElementsByTagName("RNAV2")[0].\
                getAttribute("BEACONRADIAL")),'.0f'),3)])
  data.append([c,n,7,10,i+2,format(float(line.getElementsByTagName("ToPoint")[0].getElementsByTagName("RNAV2")[0].\
                getAttribute("BEACONDISTANCENM")),'.1f')])
  data.append([l,n,7,11,i+2,line.getElementsByTagName("ALTERNATEIDENT")[0].firstChild.data.strip()[0:5]])#alternate name
  data.append([r,n,7,12,i+2,format(float(line.getElementsByTagName("ALTERNATEDISTANCE")[0].getAttribute("Value")),'.1f')])#alternate dist
  data.append([r,n,7,13,i+2,line.getElementsByTagName("MSA")[0].getAttribute("Value")])#MSA
  data.append([r,n,7,14,i+2,line.getElementsByTagName("PlannedAltitude")[0].getAttribute("Value")])#planned altitude
 block3 = FlightplanBlock([5,5],grid,text,data)

 # create block 4 with METAR and TAF information
 grid=[[[0,70,140],[55,60]],[[0,70,140],[0,55]]]
 text=[[c,b,7,0,0,"METAR Information"],[c,b,7,1,0,"TAF Information"]]
 metar=[] ; taf=[]
 style = ParagraphStyle(name='Normal',fontName='Helvetica',fontSize=7,
 leading=3*mm,spaceBefore=3*mm,spaceAfter=3*mm)
 for i in range(0,len(libs),1):
  if type(libs[i].getElementsByTagName("WXMETAR")[0].firstChild)<> type(None):
   metarString=str(libs[i].getElementsByTagName("WXMETAR")[0].firstChild.data.strip())
   metarString=metarString.lstrip("=")
   metarString=metarString.replace("=","=<br/>")
   metar.append(Paragraph(metarString,style))
  if type(libs[i].getElementsByTagName("WXALLTAF")[0].firstChild)<> type(None):
   tafString = str(libs[i].getElementsByTagName("WXALLTAF")[0].firstChild.data.strip())
   tafString=tafString.lstrip("=")
   tafString=tafString.replace("=","=<br/>")
   taf.append(Paragraph(tafString,style))
 data=[metar,taf]
 block4 = MetarTafBlock([152,145],grid,text,data)

 # create block 5 with Departure information
 grid=[[[0,30,110,125,140],[35,40]],
       [[0,10,30,40,60,80,95,110,125,140],[30,35]],
       [[0,10,30,40,60,80,95,110,125,140],[25,30]],
       [[0,10,30,40,60,80,95,110,125,140],[20,25]],
       [[0,140],[0,20]]]
 text=[[c,n,7,4,1,"Radio Navaids"],[c,n,7,5,1,"Ident"],[c,n,7,6,1,"Freq"],
       [c,n,7,7,1,"Radial"],[c,n,7,8,1,"Distance"]]
 data=[[c,b,7,0,0,"Departure"],
       [c,b,7,1,0,meta.getElementsByTagName("Departure")[0].getElementsByTagName("StringIdent")[0].firstChild.data.strip()[0:50]],
       [c,b,7,2,0,meta.getElementsByTagName("Departure")[0].getElementsByTagName("FriendlyShortname")[0].firstChild.data.strip()[0:4]],
       [c,b,7,3,0,meta.getElementsByTagName("Departure")[0].getElementsByTagName("Elevation")[0].firstChild.data.strip()+" ft"],
       [c,n,7,4,2,"Radio Navaid 1:"],
       [c,n,7,5,2,meta.getElementsByTagName("Departure")[0].getElementsByTagName("RNAV1")[0].getAttribute("BEACONIDENT")],
       [c,n,7,6,2,meta.getElementsByTagName("Departure")[0].getElementsByTagName("RNAV1")[0].getAttribute("BEACONFREQUENCY")],
       [c,n,7,7,2,str.zfill(format(float(meta.getElementsByTagName("Departure")[0].getElementsByTagName("RNAV1")[0].\
                  getAttribute("BEACONRADIAL")),'.0f'),3)],
       [r,n,7,8,2,format(float(meta.getElementsByTagName("Departure")[0].getElementsByTagName("RNAV1")[0].\
                  getAttribute("BEACONDISTANCENM")),'.1f')+" NM"],
       [c,n,7,4,3,"Radio Navaid 2:"],
       [c,n,7,5,3,meta.getElementsByTagName("Departure")[0].getElementsByTagName("RNAV2")[0].getAttribute("BEACONIDENT")],
       [c,n,7,6,3,meta.getElementsByTagName("Departure")[0].getElementsByTagName("RNAV2")[0].getAttribute("BEACONFREQUENCY")],
       [c,n,7,7,3,str.zfill(format(float(meta.getElementsByTagName("Departure")[0].getElementsByTagName("RNAV2")[0].\
                  getAttribute("BEACONRADIAL")),'.0f'),3)],
       [r,n,7,8,3,format(float(meta.getElementsByTagName("Departure")[0].getElementsByTagName("RNAV2")[0].\
                  getAttribute("BEACONDISTANCENM")),'.1f')+" NM"],
       [c,n,7,0,1,"COM"],[c,n,7,2,1,"COM"],[c,n,7,0,2,"COM"],[c,n,7,2,2,"COM"],
       [c,n,7,0,3,"COM"],[c,n,7,2,3,"COM"],[c,n,7,1,1,"< No Freq >"],
       [c,n,7,3,1,"< No Freq >"],[c,n,7,1,2,"< No Freq >"],
       [c,n,7,3,2,"< No Freq >"],[c,n,7,1,3,"< No Freq >"],
       [c,n,7,3,3,"< No Freq >"]]
 # for the COM Frequencies that do exist print the Name and the Frequency
 ComFreqs=meta.getElementsByTagName("Departure")[0].\
 getElementsByTagName("DetailedObjectInfo")[0].\
 getElementsByTagName("Communications")
 aaa=0 
 for bbb in ComFreqs:
  if bbb.getElementsByTagName("COMM"):
   for ccc in bbb.getElementsByTagName("COMM"):
    data[14+aaa][5]=ccc.getAttribute("CommType")
    data[20+aaa][5]=ccc.getAttribute("Freq1")
    aaa=aaa+1
    if aaa == 6:  # print not more than 6 Frequencies
     break
 remarks=[]
 style = ParagraphStyle(name='Normal',fontName='Helvetica',fontSize=7,\
 spaceBefore=0,spaceAfter=1,firstLineIndent=-5*mm,lineIndent=0*mm,autoLeading="min")
 try:
  comments=meta.getElementsByTagName("Departure")[0].\
      getElementsByTagName("DetailedObjectInfo")[0].\
      getElementsByTagName("Remarks")[0].\
      getElementsByTagName("Remark")
  for iii in comments:
   remarkTypeString = str(iii.getAttribute("RemarkType")+": ")
   remarkTextString = str(iii.getAttribute("RemarkText")+"<br/>")
   remarks.append(Paragraph(remarkTypeString.lstrip(": ")+remarkTextString,style))
 except:
   remarks.append(Paragraph("no Comments for this Airfield <br/>",style))
   # maybe,there are no Comments, so just go on ...
 block5 = DepartureArrivalBlock([152,105],grid,text,data,remarks)

# create block 6 with Arrival information
 data=[[c,b,7,0,0,"Arrival"],
       [c,b,7,1,0,meta.getElementsByTagName("Arrival")[0].getElementsByTagName("StringIdent")[0].firstChild.data.strip()[0:50]],
       [c,b,7,2,0,meta.getElementsByTagName("Arrival")[0].getElementsByTagName("FriendlyShortname")[0].firstChild.data.strip()[0:4]],
       [c,b,7,3,0,meta.getElementsByTagName("Arrival")[0].getElementsByTagName("Elevation")[0].firstChild.data.strip()+" ft"],
       [c,n,7,4,2,"Radio Navaid 1:"],
       [c,n,7,5,2,meta.getElementsByTagName("Arrival")[0].getElementsByTagName("RNAV1")[0].getAttribute("BEACONIDENT")],
       [c,n,7,6,2,meta.getElementsByTagName("Arrival")[0].getElementsByTagName("RNAV1")[0].getAttribute("BEACONFREQUENCY")],
       [c,n,7,7,2,str.zfill(format(float(meta.getElementsByTagName("Arrival")[0].getElementsByTagName("RNAV1")[0].\
                  getAttribute("BEACONRADIAL")),'.0f'),3)],
       [r,n,7,8,2,format(float(meta.getElementsByTagName("Arrival")[0].getElementsByTagName("RNAV1")[0].\
                  getAttribute("BEACONDISTANCENM")),'.1f')+" NM"],
       [c,n,7,4,3,"Radio Navaid 2:"],
       [c,n,7,5,3,meta.getElementsByTagName("Arrival")[0].getElementsByTagName("RNAV2")[0].getAttribute("BEACONIDENT")],
       [c,n,7,6,3,meta.getElementsByTagName("Arrival")[0].getElementsByTagName("RNAV2")[0].getAttribute("BEACONFREQUENCY")],
       [c,n,7,7,3,str.zfill(format(float(meta.getElementsByTagName("Arrival")[0].getElementsByTagName("RNAV2")[0].\
                  getAttribute("BEACONRADIAL")),'.0f'),3)],
       [r,n,7,8,3,format(float(meta.getElementsByTagName("Arrival")[0].getElementsByTagName("RNAV2")[0].\
                  getAttribute("BEACONDISTANCENM")),'.1f')+" NM"],
       [c,n,7,0,1,"COM"],[c,n,7,2,1,"COM"],[c,n,7,0,2,"COM"],
       [c,n,7,2,2,"COM"],[c,n,7,0,3,"COM"],[c,n,7,2,3,"COM"],
       [c,n,7,1,1,"< No Freq >"],[c,n,7,3,1,"< No Freq >"],
       [c,n,7,1,2,"< No Freq >"],[c,n,7,3,2,"< No Freq >"],
       [c,n,7,1,3,"< No Freq >"],[c,n,7,3,3,"< No Freq >"]]

 # for the COM Frequencies that do exist print the Name and the Frequency
 ComFreqs=meta.getElementsByTagName("Arrival")[0].\
 getElementsByTagName("DetailedObjectInfo")[0].\
 getElementsByTagName("Communications")
 aaa=0 
 for bbb in ComFreqs:
  if bbb.getElementsByTagName("COMM"):
   for ccc in bbb.getElementsByTagName("COMM"):
    data[14+aaa][5]=ccc.getAttribute("CommType")
    data[20+aaa][5]=ccc.getAttribute("Freq1")
    aaa=aaa+1
    if aaa == 6:   # print not more than 6 Frequencies
     break
 remarks=[]
 style = ParagraphStyle(name='Normal',fontName='Helvetica',fontSize=7,\
 spaceBefore=0,spaceAfter=1,firstLineIndent=-5*mm,lineIndent=0*mm,autoLeading="min")
 try:
  comments=meta.getElementsByTagName("Arrival")[0].\
      getElementsByTagName("DetailedObjectInfo")[0].\
      getElementsByTagName("Remarks")[0].\
      getElementsByTagName("Remark")
  for iii in comments:
   remarkTypeString = str(iii.getAttribute("RemarkType")+": ")
   remarkTextString = str(iii.getAttribute("RemarkText")+"<br/>")
   remarks.append(Paragraph(remarkTypeString.lstrip(": ")+remarkTextString,style))
 except:
   remarks.append(Paragraph("no Comments for this Airfield <br/>",style))
   # maybe,there are no Comments, so just go on ...
 block6 = DepartureArrivalBlock([152, 65],grid,text,data,remarks)

 # create block 7 with Fuel plan information
 grid=[[[0,80],[55,60]]]
 for i in range(50,-1,-5): grid.append([[0,60,72,80],[i,i+5]])
 data=[[r,n,7,1, 1,format(float(fuel.getElementsByTagName("ContingencyFuel")[0].getAttribute("Percentage")),'.0f')],
       [r,n,7,1, 2,format(float(fuel.getElementsByTagName("ReserveFuel")[0].getAttribute("Duration")),'.0f')],
       [r,n,7,1, 3,format(float(fuel.getElementsByTagName("LongestAlternateDistance")[0].getAttribute("Value")),'.1f')],
       [r,n,7,1, 4,format(float(fuel.getElementsByTagName("TaxiAndDepartureFuel")[0].getAttribute("Value")),'.1f')],
       [r,n,7,1, 5,format(float(fuel.getElementsByTagName("TotalTripFuel")[0].getAttribute("Value")),'.1f')],
       [r,n,7,1, 6,format(float(fuel.getElementsByTagName("ArrivalAndTaxiFuel")[0].getAttribute("Value")),'.1f')],
       [r,n,7,1, 7,format(float(fuel.getElementsByTagName("AlternateApproachFuel")[0].getAttribute("Value")),'.1f')],
       [r,n,7,1, 8,format(float(fuel.getElementsByTagName("ContingencyFuel")[0].getAttribute("Value")),'.1f')],
       [r,n,7,1, 9,format(float(fuel.getElementsByTagName("ReserveFuel")[0].getAttribute("Value")),'.1f')],
       [r,n,7,1,10,format(float(fuel.getElementsByTagName("LongestAlternateFuel")[0].getAttribute("Value")),'.1f')],
       [r,b,7,1,11,format(float(fuel.getElementsByTagName("TotalFuel")[0].getAttribute("Value")),'.1f')],
       [l,n,7,2, 1,"%"],
       [l,n,7,2, 2,fuel.getElementsByTagName("ReserveFuel")[0].getAttribute("DurationUnit")],
       [l,n,7,2, 3,fuel.getElementsByTagName("LongestAlternateDistance")[0].getAttribute("Unit")],
       [l,n,7,2, 4,fuel.getElementsByTagName("TaxiAndDepartureFuel")[0].getAttribute("Unit")],
       [l,n,7,2, 5,fuel.getElementsByTagName("TotalFuel")[0].getAttribute("Unit")],
       [l,n,7,2, 6,fuel.getElementsByTagName("ArrivalAndTaxiFuel")[0].getAttribute("Unit")],
       [l,n,7,2, 7,fuel.getElementsByTagName("AlternateApproachFuel")[0].getAttribute("Unit")],
       [l,n,7,2, 8,fuel.getElementsByTagName("ReserveFuel")[0].getAttribute("Unit")],
       [l,n,7,2, 9,fuel.getElementsByTagName("AlternateApproachFuel")[0].getAttribute("Unit")],
       [l,n,7,2,10,fuel.getElementsByTagName("LongestAlternateFuel")[0].getAttribute("Unit")],
       [l,b,7,2,11,fuel.getElementsByTagName("TotalFuel")[0].getAttribute("Unit")]]
 text=[[c,b,7,0, 0,"Fuel calculation"],
       [r,n,7,0, 1,"contingency percentage of trip fuel:"],
       [r,n,7,0, 2,"final reserve time:"],
       [r,n,7,0, 3,"longest distance to alternate:"],
       [r,n,7,0, 4,"taxi and departure fuel:"],
       [r,n,7,0, 5,"total trip fuel:"],
       [r,n,7,0, 6,"arrival and taxi fuel:"],
       [r,n,7,0, 7,"alternate approach fuel:"],
       [r,n,7,0, 8,"contingency fuel ("+data[0][5]+"% of trip fuel):"],
       [r,n,7,0, 9,"final reserve fuel from final reserve time:"],
       [r,n,7,0,10,"fuel required for longest distance to alternate:"],
       [r,b,7,0,11,"total fuel required for the trip:"]]
 block7 = FlightplanBlock([152,5],grid,text,data)

 # create block 8 with weight and balance chart
 grid=[[[0,60],[55,60]],[[0,60],[0,55]]]
 wbPoints = []
 for i in wbMomentLimits.childNodes:
  xValue = float(i.getElementsByTagName("XValue_Moment")[0].getAttribute("Value"))
  yValue = float(i.getElementsByTagName("YValue_Weight")[0].getAttribute("Value"))
  xUnit =  str(i.getElementsByTagName("XValue_Moment")[0].getAttribute("Unit"))
  yUnit =  str(i.getElementsByTagName("YValue_Weight")[0].getAttribute("Unit"))
  wbPoints.append((xValue,yValue))
 xMin = xMax = wbPoints[0][0] ; yMin = yMax = wbPoints[0][1]
 for i in range(len(wbPoints)):
    if xMin >= wbPoints[i][0]: xMin = wbPoints[i][0]
    if xMax <= wbPoints[i][0]: xMax = wbPoints[i][0]
    if yMin >= wbPoints[i][1]: yMin = wbPoints[i][1]
    if yMax <= wbPoints[i][1]: yMax = wbPoints[i][1]
 text=[[c,b,7,0, 0,"Weight&Balance Chart: X="+xUnit+" Y="+yUnit]]
 xMed = (xMin + xMax)/2
 yMed = (yMin + yMax)/2
 expCount = 0 # we start a very complex round function 
 while abs(xMed) < 1.0 or abs(xMed) > 10.0:
  if abs(xMed) < 1.0: expCount-=1 ; xMed=xMed*10
  if abs(xMed) > 1.0: expCount+=1 ; xMed=xMed/10
 xMin = round(xMin*10**-expCount,2)*10**expCount
 xMed = round(xMed,2)*10**expCount
 xMax = round(xMax*10**-expCount,2)*10**expCount
 expCount = 0 # we start a very complex round function 
 while abs(yMed) < 1.0 or abs(yMed) > 10.0:
  if abs(yMed) < 1.0: expCount-=1 ; yMed=yMed*10
  if abs(yMed) > 1.0: expCount+=1 ; yMed=yMed/10
 yMin = round(yMin*10**-expCount,2)*10**expCount
 yMed = round(yMed,2)*10**expCount
 yMax = round(yMax*10**-expCount,2)*10**expCount
 planeTotalWeightValue= round(float(weightAndBalance.getElementsByTagName("WBData")[0].\
 getElementsByTagName("PlaneTotalWeight")[0].getAttribute("Value")),1)
 planeTotalMomentValue= round(float(weightAndBalance.getElementsByTagName("WBData")[0].\
 getElementsByTagName("PlaneTotalMoment")[0].getAttribute("Value")),1)
 WBDataRecord = weightAndBalance.getElementsByTagName("WBData")[0].childNodes
 for i in range(len(WBDataRecord)):
  if str(WBDataRecord[i].getAttribute("WBDescription")) == "Fuel":
    FuelWeight = WBDataRecord[i].getElementsByTagName("Weight")[0].getAttribute("Value")
    FuelMoment = WBDataRecord[i].getElementsByTagName("Moment")[0].getAttribute("Value")   
 x1 = float(planeTotalMomentValue)
 y1 = float(planeTotalWeightValue)
 x2 = float(planeTotalMomentValue) - float(FuelMoment)
 y2 = float(planeTotalWeightValue) - float(FuelWeight)
 data = [(tuple(wbPoints[:])),((x1,y1),(x2,y2))]
 block8 = WeightAndBalanceBlock([232,5],grid,text,data,xMin,xMed,xMax,yMin,yMed,yMax)

 # get the PDF Filename from the XML Data
 filename="Navlog_from_"+meta.getElementsByTagName("Departure")[0].\
           getElementsByTagName("FriendlyShortname")[0].\
           firstChild.data.strip()[0:4]+"_to_"+\
           meta.getElementsByTagName("Arrival")[0].\
           getElementsByTagName("FriendlyShortname")[0].\
           firstChild.data.strip()[0:4]+".pdf"
 # draw page 1
 page = canvas.Canvas(filename,pagesize=landscape(A4))
 page.setFont("Helvetica-Bold", 7)
 page.drawString(050,584,">>>! Close your flight plan with Frankfurt Aeronautical Informaton Service Center: +49 69 780 72 500 !<<<")
 page.drawString(445,584,"individual MET Briefing from within Germany: 0900 1077 220 - from other Countries: +49 1805 250 123 to 126")
 block1.drawTemplate(page); block1.drawText(block1.data);  block1.positionReset()
 block2.drawTemplate(page); block2.drawText(block2.data);  block2.positionReset()
 block3.drawTemplate(page); block3.drawText(block3.data);  block3.positionReset()
 block4.drawTemplate(page); block4.drawFrame(block4.data); block4.positionReset()
 block5.drawTemplate(page); block5.drawText(block5.data);  block5.drawFrame(); block5.positionReset()
 block6.drawTemplate(page); block6.drawText(block6.data);  block6.drawFrame(); block6.positionReset()
 block7.drawTemplate(page); block7.drawText(block7.data);  block7.positionReset()
 block8.drawTemplate(page); block8.drawChart(block8.data); block8.positionReset()
 page.showPage()

# create page 2 with waypoint coordinates
 grid=[[[0,141],[85,90]]]
 for i in range(80,-1,-5):
  grid.append([[0,6,34,87,141],[i,i+5]])
 text=[[c,b,8,0,0,"Waypoint Coordinate Block"],[c,b,8,0,1,"No"],[c,b,8,1,1,"Name"],[c,b,8,2,1,"Latitude"],[c,b,8,3,1,"Longitude"]]
 data=[]
 for i,line in enumerate(libs):
  data.append([c,n,8,0,i+2,line.getAttribute("LibID")])#leg number
  data.append([c,n,8,1,i+2,line.getElementsByTagName("ToPoint")[0].\
   getElementsByTagName("FriendlyShortname")[0].firstChild.data.strip()])
  data.append([c,n,8,2,i+2,ConvertLatLon("lat",float(line.getElementsByTagName("ToPoint")[0].\
   getElementsByTagName("Latitude")[0].firstChild.data.strip()),0)])
  data.append([c,n,8,3,i+2,ConvertLatLon("lon",float(line.getElementsByTagName("ToPoint")[0].\
   getElementsByTagName("Longitude")[0].firstChild.data.strip()),0)])
 block9 = FlightplanBlock([5,115],grid,text,data)
 block9.drawTemplate(page)
 block9.drawText(block9.data)
 block9.positionReset()
 page.showPage()

 # create n pages with with NOTAM Infos
 notamtype = {\
 "LA":"Approach Lighting System","LB":"Aerodrome Beacon","LC":"Runway Centerline Lights",\
 "LD":"Landing Direction Indicator Lights","LE":"Runway Edge Lights","LF":"Sequneced Flashing Lights",\
 "LG":"Pilot Controlled Lights","LH":"High Intensity Runway Lights","LI":"Runway End Identifier Lights",\
 "LJ":"Runway Alignment Indicator Lights","LK":"Category II Components of Approach lighting System",\
 "LL":"Low Intensity Runway Lights","LM":"Medium Intensity Runway Lights","LP":"Precision Approach Path Indicator (PAPI)",\
 "LR":"All Landing Area Lighting Facilities","LS":"Stopway Lights","LT":"Threshold Lights",\
 "LV":"Visual Approach Slope Indicator System","LW":"Heliport Lighting","LX":"Taxiway Centerline Lights",\
 "LY":"Taxiway Edge Lights","LZ":"Runway Touchdown Zone Lights","MA":"Movement Area","MB":"Bearing Strength",\
 "MC":"Clearway","MD":"Declared Distances","MH":"Runway Arresting Gear","MK":"Parking Area",\
 "MM":"Daylight Markings","MN":"Apron","MO":"Stop Bars","MP":"Aircraft Stands","MR":"Runway",\
 "MS":"Stopway","MT":"Threshold","MU":"Runway Turning Bay","MW":"Strip","MX":"Taxiway","MY":"Rapid Exit Taxiway",\
 "FA":"Aerodrome","FB":"Braking Action Measurement Equipment","FC":"Ceiling Measurement Equipment",\
 "FD":"Docking System","FE":"Oxygen","FF":"Fire Fighting and Rescue","FG":"Ground Movement Control",\
 "FH":"Helicopter Alighting Area/Platform","FI":"Aircraft De-icing","FJ":"Oils",\
 "FL":"Landing Direction Indicator","FM":"Meteorological Service","FO":"Fog Dispersal System",\
 "FP":"Heliport","FS":"Snow Removal System","FT":"Transmissometer","FU":"Fuel Availability",\
 "FW":"Wind Direction Indicator","FZ":"Customs","CA":"Air/Ground Communications","CB":"ADS-B",\
 "CC":"ADS-C","CD":"CPDLC/ADS","CE":"En Route Surveillance Radar","CD":"Ground Controlled Approach System (GCA)",\
 "CL":"Selective Calling System (SELCAL)","CM":"Surface Movement Radar","CP":"Precision Approach Radar",\
 "CR":"Surveillance Radar Element of Precision Approach Radar System","CS":"Secondary Surveillance Radar (SSR)",\
 "CT":"Terminal Area Surveillance Radar (TAR)","IC":"Instrument Landing System (ILS)",\
 "ID":"DME associated with ILS","IG":"Glide Path (ILS)","II":"Inner Marker","IL":"Localizer",\
 "IM":"Middle Marker","IN":"Localizer not associated with ILS","IO":"Outer Marker",\
 "IS":"ILS Category I","IT":"ILS Category II","IU":"ILS Category III","IW":"Microwave Landing System",\
 "IX":"Locator, Outer (ILS)","IY":"Locator, Middle (ILS)","GA":"GNSS Airfield Specific Operations",\
 "GN":"GNSS Aera Wide Operations","NA":"All Radio Navigation Facilities","NB":"Nondirectional Beacons",\
 "NC":"DECCA","ND":"Distacne Measuring Equipment (DME)","NF":"Fan Marker","NG":"GPS",\
 "NL":"Locator","NM":"VOR/DME","NN":"TACAN","NO":"OMEGA","NT":"VORTAC","NV":"VOR",\
 "NX":"Direction Finding Station","AA":"Minimum Altitude","AC":"Class B,C,D or E Surface Area",\
 "AD":"Air Defence Identification Zone (ADIZ)","AE":"Control Aera","AF":"Flight Information Region",\
 "AH":"Upper Control Area","AL":"Minimum Usable Flight Level","AN":"Area Navigation Route",\
 "AO":"Oceanic Control Area (OCA)","AP":"Reporting Point","AR":"ATS Route","AT":"Class B Airspace",\
 "AU":"Upper Flight Information Region (UIR)","AV":"Upper Advisory Area (UDA)",\
 "AX":"Intersection (INT)","AZ":"Aerodrome Traffic Zone (ATZ)","SA":"Automatic Terminal Information Service (ATIS)",\
 "SB":"ATS Reporting Office","SC":"Area Control Centre (ACC)","SE":"Flight Information Service (FIS)",\
 "SF":"Aerodrome Flight Information Service","SL":"Flow Control Centre","SO":"Oceanic Area Control Centre",\
 "SP":"Approach Control Centre","SS":"Flight Service Station","ST":"Aerodrome Control Tower (TWR)",\
 "SU":"Upper Area Control Centre (UAC)","SV":"VOLMET Broadcast","SY":"Upper Advisory Service",\
 "PA":"Standard Intrument Arrival (STAR)","PB":"Standard VFR Arrival","PC":"Contingency Procedures",\
 "PD":"Standard Instrument Departure","PE":"Standard VFR Departure","PF":"Flow Control Procedure",\
 "PH":"Holding Procedure","PI":"Instrument Approach Procedure","PK":"VFR Approach Procedure",\
 "PP":"Obstacle Clearance Limit","PM":"Aerodrome Operating Minima","PN":"Noise Operating Restrictions",\
 "PR":"Radio Failure Procedure","PT":"Transition Altitude","PU":"Missed Approach Procedure",\
 "PX":"Minimum Holding Altitude","PZ":"ADIZ Procedure","RA":"Airspace Reservation",\
 "RD":"Danger Area","RM":"Military Operating Area","RO":"Overflying of ...","RP":"Prohibited Area",\
 "RR":"Restricted Area","RT":"Temporary Restricted Area","WA":"Air Display","WB":"Aerobatics",\
 "WC":"Captive Balloon or Kite","WD":"Demolition of Explosives","WE":"Exercises (specify)",\
 "WF":"Air Refueling","WG":"Glider Flying","WH":"Blasting","WJ":"Banner/Target Towing",\
 "WL":"Ascent of Free Balloon","WM":"Missile, Gun or Rocket Firing","WP":"Parachute Jumping Exercise (PJE)",\
 "WR":"Radioactive materials or Toxic Chemicals","WS":"Burning or Blowing Gas","WT":"Mass Movement of Aircraft",\
 "WU":"Unmanned Aircraft","WV":"Formation Flight","WW":"Sig Volcanic Activity","WZ":"Model Flying",\
 "OA":"Aeronautical Information Service","OB":"Obstacle (specify Details)",\
 "OE":"Aircraft Entry Requirements","OL":"Obstacle Lights On ...","OR":"Rescue Coordination Centre",\
 "XX":"Plain Language"\
 }
 notams=[] ; num_notams=0 ; ActiveFromDate=[] ; ActiveToDate=[] 
 for iii in range(len(libs)):
  for hhh in libs[iii].getElementsByTagName("NOTAMSInvolved")[0].getElementsByTagName("NOTAM"):
   if hhh.getElementsByTagName("NOTAMCode23FilterYN")[0].firstChild.data.strip()[0:1] == "N":   
    style = ParagraphStyle(name='Normal',fontName='Helvetica-Bold',fontSize=7,leading=0*mm,spaceBefore=6*mm,spaceAfter=3*mm)
    notamstring=hhh.getElementsByTagName("NOTAMName")[0].firstChild.data.strip()
    notams.append(Paragraph(notamstring,style)) ;num_notams=num_notams+1
    style = ParagraphStyle(name='Normal',fontName='Helvetica',fontSize=7,leading=0*mm,spaceBefore=0*mm,spaceAfter=3*mm)
    for i in range(0,len(notamstring),1):
     if notamstring[i] == "(": notams.append(Paragraph("Type: "+ notamtype[notamstring[i+1:i+3]],style)) # transfer code to clear text
    notamstring="Location: LAT:"+hhh.getElementsByTagName("NOTAMEntryPoint")[0].getElementsByTagName("Latitude")[0].firstChild.data.strip()
    notamstring=notamstring+" LON:"+hhh.getElementsByTagName("NOTAMEntryPoint")[0].getElementsByTagName("Longitude")[0].firstChild.data.strip()
    notams.append(Paragraph(notamstring,style)) ;num_notams=num_notams+1
    ActiveFromDate= hhh.getElementsByTagName("NOTAMActiveFromDateTime")[0].firstChild.data.strip()
    if ActiveFromDate != "PERM":
     ActiveFromDate = ActiveFromDate[0:2]+"/"+ActiveFromDate[2:4]+"/"+ActiveFromDate[4:6]+" "+ActiveFromDate[6:10]+" UTC"
    ActiveToDate = hhh.getElementsByTagName("NOTAMActiveUpToDateTime")[0].firstChild.data.strip()
    if ActiveToDate != "PERM":
     ActiveToDate = ActiveToDate[0:2]+"/"+ActiveToDate[2:4]+"/"+ActiveToDate[4:6]+" "+ActiveToDate[6:10]+" UTC"
    notamstring="Active from: "+ActiveFromDate+" to "+ActiveToDate
    notams.append(Paragraph(notamstring,style)) ;num_notams=num_notams+1
    notamstring=hhh.getElementsByTagName("NOTAMELine")[0].firstChild.data.strip()
    notamstring=notamstring.replace("{lf}"," ")
    style = ParagraphStyle(name='Normal',fontName='Helvetica',fontSize=7,leading=3*mm,spaceBefore=0*mm,spaceAfter=3*mm)
    notams.append(Paragraph(notamstring,style)) ;num_notams=num_notams+1  
 width=140 ; height = 200 ; reqheight=0
 for aaa in range(num_notams):
  w,h = notams[aaa].wrap(width,height)
  reqheight=reqheight+h
  # print aaa,w,h,height,reqheight
 while reqheight > (height+2):
  fnotam=Frame(5*mm,5*mm,width*mm,height*mm,showBoundary=1,\
  leftPadding=1*mm,rightPadding=1*mm,topPadding=1*mm,bottomPadding=1*mm)
  fnotam.addFromList(notams,page) # print out all NOTAMs to Frame fnotam
  fnotam=Frame(152*mm,5*mm,width*mm,height*mm,showBoundary=1,leftPadding=1*mm,\
  rightPadding=1*mm,topPadding=1*mm,bottomPadding=1*mm)
  fnotam.addFromList(notams,page) # print out all NOTAMs to Frame fnotam
  page.showPage()
  reqheight=reqheight-(height+2)

  
 page.save()
 # open the file with Acrobat Reader
 try: osString = "start "+filename ; system(osString)
 except IOError: print("Acrobat Reader hat die Datei noch geoeffnet!")
 except: pass
  
  
