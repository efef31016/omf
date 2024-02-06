import datetime
import calendar
import operator
import copy
import math

class PRISM:
    def __init__(self, prismDRDict):
        self.prismDRDict = prismDRDict
        self._prepare_data()
        
    def _prepare_data(self):
        """Prepare necessary data from the initial dictionary."""
        start_month = self.prismDRDict['startMonth']
        stop_month = self.prismDRDict['stopMonth']
        self.start_date, self.stop_date, self.start_index, self.stop_index, self.day_count = self.calculate_date_ranges(start_month, stop_month)
        self.handle_rate_structure()
        
    def calculate_date_ranges(self, start_month, stop_month):
        """Calculate start and stop dates, indices, and day counts."""
        start_date = datetime.date(2009, start_month, 1)
        last_day = calendar.monthrange(2009, stop_month)[1]
        stop_date = datetime.date(2009, stop_month, last_day)
        start_index = (start_date - datetime.date(2009, 1, 1)).days * 24
        stop_index = (stop_date - datetime.date(2009, 1, 1)).days * 24 + 23
        day_count = (stop_date - start_date).days + 1
        return start_date, stop_date, start_index, stop_index, day_count

    def handle_rate_structure(self):
        """Adjust hours on and off peak based on the rate structure."""
        if self.prismDRDict['rateStructure'] != '24hourly':
            self.prismDRDict['numHoursOn'] = self.prismDRDict['stopHour'] - self.prismDRDict['startHour'] + 1
            self.prismDRDict['numHoursOff'] = (24 - self.prismDRDict['numHoursOn'])
        # '2tierCPP' 或 'PTR'，尖峰時段開啟和關閉的小時數是基於特定天數（numCPPDays）的計算
        if self.prismDRDict['rateStructure'] == '2tierCPP'  or self.prismDRDict['rateStructure'] == 'PTR':
            self.prismDRDict['hrsOnPeakWCPP'] = self.prismDRDict['numHoursOn'] * self.prismDRDict['numCPPDays']
            self.prismDRDict['hrsOffPeakWCPP'] = self.prismDRDict['numHoursOff'] * self.prismDRDict['numCPPDays']
            self.prismDRDict['hrsOnPeakWOCPP'] = ((self.prismDRDict['stopHour'] - self.prismDRDict['startHour'] + 1) * self.prismDRDict['dayCount']) - self.prismDRDict['hrsOnPeakWCPP']
            self.prismDRDict['hrsOffPeakWOCPP'] = ((self.prismDRDict['dayCount'] * 24) - self.prismDRDict['hrsOnPeakWOCPP']) - self.prismDRDict['hrsOffPeakWCPP']
            self.prismDRDict['hrsOnPeakPerMonthWCPP'] = float(self.prismDRDict['hrsOnPeakWCPP']) / float(self.prismDRDict['numMonths'])
            self.prismDRDict['hrsOffPeakPerMonthWCPP'] = float(self.prismDRDict['hrsOffPeakWCPP']) / float(self.prismDRDict['numMonths'])
        # '24hourly'，只有一小時是特定價格，因此設定 hrsOn 為總天數乘以1，hrsOff 為總天數乘以23
        elif self.prismDRDict['rateStructure'] == '24hourly':
            self.prismDRDict['hrsOn'] = 1 * self.prismDRDict['dayCount'] #Only one hour per day at a given price
            self.prismDRDict['hrsOff'] = 23 * self.prismDRDict['dayCount']
            self.prismDRDict['numHoursOn'] = 1 #Only one hour at a given price each day
            self.prismDRDict['numHoursOff'] = 23
        if self.prismDRDict['rateStructure'] != '24hourly':
            self.prismDRDict['hrsOnPeakPerMonthWOCPP'] = float(self.prismDRDict['hrsOnPeakWOCPP']) / float(self.prismDRDict['numMonths'])
            self.prismDRDict['hrsOffPeakPerMonthWOCPP'] = float(self.prismDRDict['hrsOffPeakWOCPP']) / float(self.prismDRDict['numMonths'])
        # Do 2tierCPP. Finds largest load days and designate them CPP days.
        if self.prismDRDict['rateStructure'] == '2tierCPP' or self.prismDRDict['rateStructure'] == 'PTR':
            self.prismDRDict['cppHours'] = []
            self.prismDRDict['cppDayIdx'] = []
            maxCount = 0
            tempLoad = list(self.prismDRDict['origLoad'])
            while maxCount < self.prismDRDict['numCPPDays']:
                maxIndex, maxLoad = max(enumerate(tempLoad), key=operator.itemgetter(1))
                maxIndex = (maxIndex // 24) * 24 #First hour of day.
                tempLoad[maxIndex:maxIndex + 24] = list([0] * 24) #Zero-ing out so that we don't consider this day again
                if self.prismDRDict['startIndex'] <= self.prismDRDict['stopIndex']:
                    if maxIndex >= self.prismDRDict['startIndex'] and maxIndex <= self.prismDRDict['stopIndex']: #max day was in DR season
                        self.prismDRDict['cppHours'].append([maxIndex+self.prismDRDict['startHour'], maxIndex+self.prismDRDict['stopHour']])
                        for idx in range(0,24):
                            self.prismDRDict['cppDayIdx'].append(maxIndex + idx)
                        maxCount+=1
                else:
                    if maxIndex >= self.prismDRDict['startIndex'] or maxIndex <= self.prismDRDict['stopIndex']: #max day was in DR season
                        self.prismDRDict['cppHours'].append([maxIndex+self.prismDRDict['startHour'], maxIndex+self.prismDRDict['stopHour']])
                        for idx in range(0,24):
                            self.prismDRDict['cppDayIdx'].append(maxIndex + idx)
                        maxCount+=1

    def calculate_energy(self):
        """Calculate energy based on rate structure."""
        self.prismDRDict['onPeakWOCPPEnergy'] = 0.0
        self.prismDRDict['offPeakWCPPEnergy'] = 0.0
        self.prismDRDict['offPeakWOCPPEnergy'] = 0.0
        self.prismDRDict['impactFactorOnPeakWOCPP'] = 0.0
        self.prismDRDict['impactFactorOffPeakWOCPP'] = 0.0
        self.prismDRDict['onPeakWCPPEnergy'] = 0.0
        self.hourlyEnergy = list([0] * 24)
        for idx, load in enumerate(self.prismDRDict['origLoad']):
            if self.prismDRDict['startIndex'] <= self.prismDRDict['stopIndex']:
                if idx >= self.prismDRDict['startIndex'] and idx <= self.prismDRDict['stopIndex']: #is hour of year in the DR season?
                    inDRSeason = 1
                else:
                    inDRSeason = 0
            else:
                if idx >= self.prismDRDict['startIndex'] or idx <= self.prismDRDict['stopIndex']: #is hour of year in the DR season?
                    inDRSeason = 1
                else:
                    inDRSeason = 0
            if inDRSeason == 1:
                hourOfDay = idx % 24
                if self.prismDRDict['rateStructure'] == '2tierCPP' or self.prismDRDict['rateStructure'] == 'PTR':
                    if idx in self.prismDRDict['cppDayIdx']:
                        if (hourOfDay >= self.prismDRDict['startHour']) and (hourOfDay <= self.prismDRDict['stopHour']):
                            self.prismDRDict['onPeakWCPPEnergy'] += load
                        else:
                            self.prismDRDict['offPeakWCPPEnergy'] += load
                    else:
                        if (hourOfDay >= self.prismDRDict['startHour']) and (hourOfDay <= self.prismDRDict['stopHour']):
                            self.prismDRDict['onPeakWOCPPEnergy'] += load
                        else:
                            self.prismDRDict['offPeakWOCPPEnergy'] += load
                elif self.prismDRDict['rateStructure'] == '24hourly':
                    self.hourlyEnergy[hourOfDay] += load
                else:
                    if (hourOfDay >= self.prismDRDict['startHour']) and (hourOfDay <= self.prismDRDict['stopHour']):
                        self.prismDRDict['onPeakWOCPPEnergy'] += load
                    else:
                        self.prismDRDict['offPeakWOCPPEnergy'] += load

    def outside_load_not_used(self):
        if self.prismDRDict['rateStructure'] == '2tierCPP' or self.prismDRDict['rateStructure'] == 'PTR':
            self.prismDRDict['totalEnergy'] = self.prismDRDict['offPeakWOCPPEnergy'] + self.prismDRDict['onPeakWOCPPEnergy'] + self.prismDRDict['offPeakWCPPEnergy'] + self.prismDRDict['onPeakWCPPEnergy']
            self.prismDRDict['onPeakWCPPMonAvgkWh'] = self.prismDRDict['onPeakWCPPEnergy']/self.prismDRDict['numMonths']
            self.prismDRDict['offPeakWCPPMonAvgkWh'] = self.prismDRDict['offPeakWCPPEnergy']/self.prismDRDict['numMonths']
        elif self.prismDRDict['rateStructure'] == '24hourly':
            self.prismDRDict['totalEnergy'] = sum(self.hourlyEnergy)
            self.prismDRDict['hourlyMonAvgkWh'] = list([0]*24)
            for hour, energy in enumerate(self.hourlyEnergy):
                self.prismDRDict['hourlyMonAvgkWh'][hour] = energy/self.prismDRDict['numMonths']
            self.prismDRDict['offPeakMonAvgkWh'] = sum(self.prismDRDict['hourlyMonAvgkWh'])/self.prismDRDict['numMonths'] #For PRISM computation, defining the off-peak energy (used as elasticity baseline reference) as the average of the total energy.
        else:
            self.prismDRDict['totalEnergy'] = self.prismDRDict['offPeakWOCPPEnergy'] + self.prismDRDict['onPeakWOCPPEnergy']
        self.prismDRDict['onPeakWOCPPMonAvgkWh'] = self.prismDRDict['onPeakWOCPPEnergy']/self.prismDRDict['numMonths']
        self.prismDRDict['offPeakWOCPPMonAvgkWh'] = self.prismDRDict['offPeakWOCPPEnergy']/self.prismDRDict['numMonths']
        self.prismDRDict['totalMonAvgkWh'] = self.prismDRDict['totalEnergy']/self.prismDRDict['numMonths']

    def calculate_impact_factors(self):
        """Calculate impact factors based on the rate structure."""
        if self.prismDRDict['rateStructure'] != '24hourly':
            kWhPerHrOldOnPeakWOCPP = self.prismDRDict['onPeakWOCPPMonAvgkWh']/self.prismDRDict['hrsOnPeakPerMonthWOCPP'] # B30
            kWhPerHrOldOffPeakWOCPP = self.prismDRDict['offPeakWOCPPMonAvgkWh']/self.prismDRDict['hrsOffPeakPerMonthWOCPP'] #C30
            logFactorWOCPP = math.log(kWhPerHrOldOnPeakWOCPP/kWhPerHrOldOffPeakWOCPP) + self.prismDRDict['elasticitySubWOCPP'] * (math.log(self.prismDRDict['rateOnPeak']/self.prismDRDict['rateOffPeak'] - math.log(self.prismDRDict['rateFlat']/self.prismDRDict['rateFlat']))) #B28
            kWhPerHrOldDailyWOCPP = ((kWhPerHrOldOnPeakWOCPP * self.prismDRDict['numHoursOn']) + (kWhPerHrOldOffPeakWOCPP * self.prismDRDict['numHoursOff']))/24 #D30
            dailyNewPeakWOCPP = ((self.prismDRDict['rateOnPeak'] * self.prismDRDict['numHoursOn'] * kWhPerHrOldOnPeakWOCPP) + (self.prismDRDict['rateOffPeak'] * self.prismDRDict['numHoursOff'] * kWhPerHrOldOffPeakWOCPP)) / ((self.prismDRDict['numHoursOn'] * kWhPerHrOldOnPeakWOCPP)+(self.prismDRDict['numHoursOff'] * kWhPerHrOldOffPeakWOCPP)) #D24
            dailyOldPeakWOCPP = ((self.prismDRDict['rateFlat'] * self.prismDRDict['numHoursOn'] * kWhPerHrOldOnPeakWOCPP) + (self.prismDRDict['rateFlat'] * self.prismDRDict['numHoursOff'] * kWhPerHrOldOffPeakWOCPP)) / ((self.prismDRDict['numHoursOn'] * kWhPerHrOldOnPeakWOCPP)+(self.prismDRDict['numHoursOff'] * kWhPerHrOldOffPeakWOCPP)) #D23
            kWhPerHrNewDailyWOCPP = math.exp(math.log(kWhPerHrOldDailyWOCPP) - (self.prismDRDict['elasticityDailyWOCPP'] * (math.log(dailyOldPeakWOCPP) - math.log(dailyNewPeakWOCPP)))) #D31
            kWhPerHrNewOffPeakWOCPP =  ((24/float(self.prismDRDict['numHoursOff'])) * kWhPerHrNewDailyWOCPP) / (1+((self.prismDRDict['numHoursOn']/float(self.prismDRDict['numHoursOff'])) * math.exp(logFactorWOCPP))) #C31
            kWhPerHrNewOnPeakWOCPP  = kWhPerHrNewOffPeakWOCPP * math.exp(logFactorWOCPP) #B31
            kWhDeltaOnPeakWOCPP = kWhPerHrNewOnPeakWOCPP - kWhPerHrOldOnPeakWOCPP #B32
            kWhDeltaOffPeakWOCPP = kWhPerHrNewOffPeakWOCPP - kWhPerHrOldOffPeakWOCPP #C32
            self.prismDRDict['impactFactorOnPeakWOCPP'] = kWhDeltaOnPeakWOCPP/kWhPerHrOldOnPeakWOCPP #B33
            self.prismDRDict['impactFactorOffPeakWOCPP'] = kWhDeltaOffPeakWOCPP/kWhPerHrOldOffPeakWOCPP #C33
        if self.prismDRDict['rateStructure'] == '24hourly':
            self.prismDRDict['impactFactor24hourly'] = list([0] * 24)
            self.prismDRDict['rateOffPeak'] = self.prismDRDict['rateFlat']
            kWhPerHrOldOffPeak = self.prismDRDict['offPeakMonAvgkWh']/self.prismDRDict['hrsOff']
            for hour,energy in enumerate(self.hourlyEnergy):
                kWhPerHrOldOnPeak = self.prismDRDict['hourlyMonAvgkWh'][hour]/self.prismDRDict['hrsOn']
                logFactor = math.log(kWhPerHrOldOnPeak/kWhPerHrOldOffPeak) + self.prismDRDict['elasticitySubWOCPP'] * (math.log(self.prismDRDict['rate24hourly'][hour]/self.prismDRDict['rateOffPeak'] - math.log(self.prismDRDict['rateFlat']/self.prismDRDict['rateFlat'])))
                kWhPerHrOldDaily = ((kWhPerHrOldOnPeak * self.prismDRDict['numHoursOn']) + (kWhPerHrOldOffPeak * self.prismDRDict['numHoursOff']))/24
                dailyNewPeak = ((self.prismDRDict['rate24hourly'][hour] * self.prismDRDict['numHoursOn'] * kWhPerHrOldOnPeak) + (self.prismDRDict['rateOffPeak'] * self.prismDRDict['numHoursOff'] * kWhPerHrOldOffPeak)) / ((self.prismDRDict['numHoursOn'] * kWhPerHrOldOnPeak)+(self.prismDRDict['numHoursOff'] * kWhPerHrOldOffPeak))
                dailyOldPeak = ((self.prismDRDict['rateFlat'] * self.prismDRDict['numHoursOn'] * kWhPerHrOldOnPeak) + (self.prismDRDict['rateFlat'] * self.prismDRDict['numHoursOff'] * kWhPerHrOldOffPeak)) / ((self.prismDRDict['numHoursOn'] * kWhPerHrOldOnPeak)+(self.prismDRDict['numHoursOff'] * kWhPerHrOldOffPeak))
                kWhPerHrNewDaily = math.exp(math.log(kWhPerHrOldDaily) - (self.prismDRDict['elasticityDailyWOCPP'] * (math.log(dailyOldPeak) - math.log(dailyNewPeak))))
                kWhPerHrNewOffPeak =  ((24/float(self.prismDRDict['numHoursOff'])) * kWhPerHrNewDaily) / (1+((self.prismDRDict['numHoursOn']/float(self.prismDRDict['numHoursOff'])) * math.exp(logFactor)))
                kWhPerHrNewOnPeak  = kWhPerHrNewOffPeak * math.exp(logFactor)
                kWhDeltaOnPeak = kWhPerHrNewOnPeak - kWhPerHrOldOnPeak
                self.prismDRDict['impactFactor24hourly'][hour] = kWhDeltaOnPeak/kWhPerHrOldOnPeak

    def calculate_CPP_days(self):
        if self.prismDRDict['rateStructure'] == '2tierCPP' or self.prismDRDict['rateStructure'] == 'PTR':
            if self.prismDRDict['rateStructure'] == 'PTR':
                self.prismDRDict['rateCPP'] = self.prismDRDict['ratePTR'] + self.prismDRDict['rateFlat'] #Total value for consumer during PTR periods
            kWhPerHrOldOnPeakWCPP = self.prismDRDict['onPeakWCPPMonAvgkWh']/self.prismDRDict['hrsOnPeakPerMonthWCPP'] # B14
            kWhPerHrOldOffPeakWCPP = self.prismDRDict['offPeakWCPPMonAvgkWh']/self.prismDRDict['hrsOffPeakPerMonthWCPP'] #C14
            logFactorWCPP = math.log(kWhPerHrOldOnPeakWCPP/kWhPerHrOldOffPeakWCPP) + self.prismDRDict['elasticitySubWCPP'] * (math.log(self.prismDRDict['rateCPP']/self.prismDRDict['rateOffPeak'] - math.log(self.prismDRDict['rateFlat']/self.prismDRDict['rateFlat']))) #B12
            kWhPerHrOldDailyWCPP = ((kWhPerHrOldOnPeakWCPP * self.prismDRDict['numHoursOn']) +
                                    (kWhPerHrOldOffPeakWCPP * self.prismDRDict['numHoursOff']))/24 #D14
            dailyNewPeakWCPP = ((self.prismDRDict['rateCPP'] * self.prismDRDict['numHoursOn'] * kWhPerHrOldOnPeakWCPP) + (self.prismDRDict['rateOffPeak'] * self.prismDRDict['numHoursOff'] * kWhPerHrOldOffPeakWCPP)) / ((self.prismDRDict['numHoursOn'] * kWhPerHrOldOnPeakWCPP)+(self.prismDRDict['numHoursOff'] * kWhPerHrOldOffPeakWCPP)) #D8
            dailyOldPeakWCPP = ((self.prismDRDict['rateFlat'] * self.prismDRDict['numHoursOn'] * kWhPerHrOldOnPeakWCPP) + (self.prismDRDict['rateFlat'] * self.prismDRDict['numHoursOff'] * kWhPerHrOldOffPeakWCPP)) / ((self.prismDRDict['numHoursOn'] * kWhPerHrOldOnPeakWCPP)+(self.prismDRDict['numHoursOff'] * kWhPerHrOldOffPeakWCPP)) #D7
            kWhPerHrNewDailyWCPP = math.exp(math.log(kWhPerHrOldDailyWCPP) - (self.prismDRDict['elasticityDailyWCPP'] * (math.log(dailyOldPeakWCPP) - math.log(dailyNewPeakWCPP)))) #D15
            kWhPerHrNewOffPeakWCPP =  ((24/float(self.prismDRDict['numHoursOff'])) * kWhPerHrNewDailyWCPP) / (1+((self.prismDRDict['numHoursOn']/float(self.prismDRDict['numHoursOff'])) * math.exp(logFactorWCPP))) #C15
            kWhPerHrNewOnPeakWCPP  = kWhPerHrNewOffPeakWCPP * math.exp(logFactorWCPP) #B15
            kWhDeltaOnPeakWCPP = kWhPerHrNewOnPeakWCPP - kWhPerHrOldOnPeakWCPP #B16
            kWhDeltaOffPeakWCPP = kWhPerHrNewOffPeakWCPP - kWhPerHrOldOffPeakWCPP #C16
            self.prismDRDict['impactFactorOnPeakWCPP'] = kWhDeltaOnPeakWCPP/kWhPerHrOldOnPeakWCPP #B17
            self.prismDRDict['impactFactorOffPeakWCPP'] = kWhDeltaOffPeakWCPP/kWhPerHrOldOffPeakWCPP #C17

    def modify_load_curve(self):
        """Modify the load curve based on the impact factors."""
        self.prismDRDict['modLoad'] = list(self.prismDRDict['origLoad'])
        for idx, load in enumerate(self.prismDRDict['origLoad']):
            if self.prismDRDict['startIndex'] <= self.prismDRDict['stopIndex']:
                if idx >= self.prismDRDict['startIndex'] and idx <= self.prismDRDict['stopIndex']: #is hour of year in the DR season?
                    inDRSeason = 1
                else:
                    inDRSeason = 0
            else:
                if idx >= self.prismDRDict['startIndex'] or idx <= self.prismDRDict['stopIndex']: #is hour of year in the DR season?
                    inDRSeason = 1
                else:
                    inDRSeason = 0
            if inDRSeason == 1:
                hourOfDay  = idx % 24
                if self.prismDRDict['rateStructure'] == '2tierCPP' or self.prismDRDict['rateStructure'] == 'PTR':
                    if idx in self.prismDRDict['cppDayIdx']:
                        if (hourOfDay >= self.prismDRDict['startHour']) and (hourOfDay <= self.prismDRDict['stopHour']):
                            self.prismDRDict['modLoad'][idx] = self.prismDRDict['origLoad'][idx] * (1 + self.prismDRDict['impactFactorOnPeakWCPP'])
                        else:
                            self.prismDRDict['modLoad'][idx] = self.prismDRDict['origLoad'][idx] * (1 + self.prismDRDict['impactFactorOffPeakWCPP'])
                    else:
                        if (hourOfDay >= self.prismDRDict['startHour']) and (hourOfDay <= self.prismDRDict['stopHour']):
                            self.prismDRDict['modLoad'][idx] = self.prismDRDict['origLoad'][idx] * (1 + self.prismDRDict['impactFactorOnPeakWOCPP'])
                        else:
                            self.prismDRDict['modLoad'][idx] = self.prismDRDict['origLoad'][idx] * (1 + self.prismDRDict['impactFactorOffPeakWOCPP'])
                elif self.prismDRDict['rateStructure'] == '24hourly':
                    self.prismDRDict['modLoad'][idx] = self.prismDRDict['origLoad'][idx] * (1 + self.prismDRDict['impactFactor24hourly'][hourOfDay])
                else:
                    if (hourOfDay < self.prismDRDict['startHour']) or (hourOfDay > self.prismDRDict['stopHour']):
                        self.prismDRDict['modLoad'][idx] = self.prismDRDict['origLoad'][idx] * (1 + self.prismDRDict['impactFactorOffPeakWOCPP'])
                    else:
                        self.prismDRDict['modLoad'][idx] = self.prismDRDict['origLoad'][idx] * (1 + self.prismDRDict['impactFactorOnPeakWOCPP'])

    def process(self):
        """Main method to process the PRISM calculations."""
        self.handle_rate_structure()
        self.calculate_energy()
        self.outside_load_not_used()
        self.calculate_impact_factors()
        self.calculate_CPP_days()
        self.modify_load_curve()
        return self.prismDRDict

def DLC(DLCDict):
	# Estimate load reduction from direct load control.
	DLCDict['modLoad'] = list(DLCDict['origLoad'])
	DLCDict['whTotalPower'] = DLCDict['residenceCount'] * DLCDict['whPercentage'] * DLCDict['whRatingkW'] * DLCDict['whDutyCycle']
	DLCDict['hvacTotalPower'] = DLCDict['residenceCount'] * DLCDict['hvacPercentage'] * DLCDict['hvacRatingkW'] * DLCDict['hvacDutyCycle']
	for idx, load in enumerate(DLCDict['origLoad']):
		if idx in DLCDict['whControlHours']:
			DLCDict['modLoad'][idx] = load - DLCDict['whTotalPower']
		if idx in DLCDict['hvacControlHours']:
			DLCDict['modLoad'][idx] = load - DLCDict['hvacTotalPower']
	return DLCDict

def _prismTests():
    # Run Direct Load Control sim.
    with open('./test_load.csv') as f:
        orig_load = [float(x) for x in f.readlines()]
    orig_load_copy = copy.deepcopy(orig_load)
    outputs1 = DLC({
        'residenceCount': 2000,
        'whPercentage': 0.30,
        'hvacPercentage': 0.20,
        'whRatingkW': 9,
        'hvacRatingkW': 4,
        'whDutyCycle': 0.1,
        'hvacDutyCycle': 0.3,
        'whControlHours': [0, 1, 2, 3, 4],
        'hvacControlHours': [6, 7, 8, 9,10],
        'origLoad': orig_load}) # 8760 load values
    # Run PRISM.
    prism = PRISM({
        'rateStructure': '2tierCPP', # options: 2tierCPP, PTR, 24hourly
        'elasticitySubWOCPP': -0.09522, # Substitution elasticty during non-CPP days.
        'elasticityDailyWOCPP': -0.02302, # Daily elasticity during non-CPP days.
        'elasticitySubWCPP': -0.09698, # Substitution elasticty during CPP days. Only required for 2tierCPP
        'elasticityDailyWCPP': -0.01607, # Daily elasticity during non-CPP days. Only reuquired for 2tierCPP
        'startMonth': 9, # 1-12. Beginning month of the cooling season when the DR program will run.
        'stopMonth': 3, # 1-12. Ending month of the cooling season when the DR program will run.
        'startHour': 14, # 0-23. Beginning hour for on-peak and CPP rates.
        'stopHour': 18, # 0-23. Ending hour for on-peak and CPP rates.
        'rateFlat': 0.10, # pre-DR Time-independent rate paid by residential consumers.
        'rateOnPeak': 0.60, # Peak hour rate on non-CPP days.
        'rateOffPeak':0.01,
        'rateCPP': 1.80, # Peak hour rate on CPP days. Only required for 2tierCPP
        'rate24hourly': [0.074, 0.041, 0.020, 0.035, 0.100, 0.230, 0.391, 0.550, 0.688, 0.788, 0.859, 0.904, 0.941, 0.962, 0.980, 1.000, 0.999, 0.948, 0.904, 0.880, 0.772, 0.552, 0.341, 0.169], #Hourly energy price, only needed for 24hourly
        #'rate24hourly': [0.12, 0.054, 0.01, 0.04, 0.172, 0.436, 0.764, 1.086, 1.367, 1.569, 1.714, 1.805, 1.880, 1.923, 1.960, 2, 1.998, 1.895, 1.806, 1.757, 1.538, 1.089, 0.662, 0.313],
        'ratePTR': 2.65, # Only required for PTR. $/kWh payment to customers for demand reduction on PTR days. Value is entered as a positive value, just like the other rate values, even though it is a rebate.
        'numCPPDays': 10, # Number of CPP days in a cooling season. Only required for 2tierCPP
        'origLoad': orig_load_copy}) # 8760 load values
    outputs2 = prism.process()
        

if __name__ =="__main__":

    _prismTests()
