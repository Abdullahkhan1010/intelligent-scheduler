"""
Context Extraction Module
Converts raw sensor and system data into categorical features for Bayesian inference
"""
from datetime import datetime, time as time_type
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
import re


class TimeOfDay(str, Enum):
    """Time of day categories"""
    MORNING = "morning"      # 05:00 - 11:59
    AFTERNOON = "afternoon"  # 12:00 - 16:59
    EVENING = "evening"      # 17:00 - 20:59
    NIGHT = "night"          # 21:00 - 04:59


class LocationCategory(str, Enum):
    """Location categories"""
    HOME = "home"
    CAMPUS = "campus"
    WORK = "work"
    COMMUTE = "commute"
    UNKNOWN = "unknown"


class ActivityState(str, Enum):
    """Activity state categories"""
    STATIONARY = "stationary"
    WALKING = "walking"
    TRAVELING = "traveling"
    RUNNING = "running"
    CYCLING = "cycling"


class CalendarAvailability(str, Enum):
    """Calendar availability states"""
    FREE = "free"
    BUSY = "busy"
    TENTATIVE = "tentative"
    UNKNOWN = "unknown"


class ScreenState(str, Enum):
    """Screen interaction states"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    LOCKED = "locked"
    UNKNOWN = "unknown"


class BatteryState(str, Enum):
    """Battery level states"""
    NORMAL = "normal"      # > 30%
    LOW = "low"            # 15% - 30%
    CRITICAL = "critical"  # < 15%
    CHARGING = "charging"
    UNKNOWN = "unknown"


@dataclass
class ExtractedContext:
    """
    Normalized context object with categorical features.
    Compatible with Bayesian inference engine.
    """
    # Core temporal features
    timestamp: datetime
    time_of_day: TimeOfDay
    day_of_week: str  # Monday, Tuesday, etc.
    is_weekday: bool
    is_weekend: bool
    hour: int
    minute: int
    
    # Location and mobility
    location_category: LocationCategory
    activity_state: ActivityState
    speed_kmh: float
    is_moving: bool
    is_stationary: bool
    
    # Calendar and availability
    calendar_availability: CalendarAvailability
    
    # Device state
    screen_state: ScreenState
    battery_state: BatteryState
    battery_level: Optional[float]
    
    # Connectivity signals (soft signals)
    wifi_ssid: Optional[str]
    is_wifi_connected: bool
    is_home_wifi: bool
    is_campus_wifi: bool
    is_work_wifi: bool
    
    bluetooth_devices: List[str]
    is_car_connected: bool
    is_headphones_connected: bool
    
    # Raw activity type (for compatibility)
    raw_activity_type: str
    
    # Location vector (for compatibility with existing system)
    location_vector: Optional[str]
    
    # Data quality indicators
    has_location_data: bool
    has_calendar_data: bool
    has_battery_data: bool
    confidence_score: float  # 0.0 to 1.0, based on data completeness
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'time_of_day': self.time_of_day.value,
            'day_of_week': self.day_of_week,
            'is_weekday': self.is_weekday,
            'is_weekend': self.is_weekend,
            'hour': self.hour,
            'minute': self.minute,
            'location_category': self.location_category.value,
            'activity_state': self.activity_state.value,
            'speed_kmh': self.speed_kmh,
            'is_moving': self.is_moving,
            'is_stationary': self.is_stationary,
            'calendar_availability': self.calendar_availability.value,
            'screen_state': self.screen_state.value,
            'battery_state': self.battery_state.value,
            'battery_level': self.battery_level,
            'wifi_ssid': self.wifi_ssid,
            'is_wifi_connected': self.is_wifi_connected,
            'is_home_wifi': self.is_home_wifi,
            'is_campus_wifi': self.is_campus_wifi,
            'is_work_wifi': self.is_work_wifi,
            'bluetooth_devices': self.bluetooth_devices,
            'is_car_connected': self.is_car_connected,
            'is_headphones_connected': self.is_headphones_connected,
            'raw_activity_type': self.raw_activity_type,
            'location_vector': self.location_vector,
            'has_location_data': self.has_location_data,
            'has_calendar_data': self.has_calendar_data,
            'has_battery_data': self.has_battery_data,
            'confidence_score': self.confidence_score
        }
    
    def get_context_signature(self) -> str:
        """
        Generate a compact context signature for Bayesian grouping.
        Example: "stationary_morning_weekday_home"
        """
        return f"{self.activity_state.value}_{self.time_of_day.value}_{('weekday' if self.is_weekday else 'weekend')}_{self.location_category.value}"


class ContextExtractor:
    """
    Extracts and normalizes context features from raw sensor data.
    Handles missing data gracefully and provides confidence scores.
    """
    
    # Known WiFi patterns for location inference
    HOME_WIFI_PATTERNS = ['home', 'house', 'residence', 'family']
    CAMPUS_WIFI_PATTERNS = ['university', 'campus', 'edu', 'student', 'library']
    WORK_WIFI_PATTERNS = ['office', 'work', 'corp', 'company']
    
    # Known Bluetooth device patterns
    CAR_BLUETOOTH_PATTERNS = ['car', 'vehicle', 'audio', 'honda', 'toyota', 'bmw', 'tesla']
    HEADPHONE_PATTERNS = ['airpods', 'headphones', 'buds', 'beats', 'sony', 'bose']
    
    def __init__(self):
        self.location_confidence_threshold = 0.6
    
    def extract(self, raw_data: Dict[str, Any]) -> ExtractedContext:
        """
        Main extraction method. Converts raw sensor data into ExtractedContext.
        
        Args:
            raw_data: Dictionary containing raw sensor and system data
            
        Returns:
            ExtractedContext object with normalized categorical features
        """
        # Extract timestamp
        timestamp = self._extract_timestamp(raw_data)
        
        # Temporal features
        time_of_day = self._extract_time_of_day(timestamp)
        day_of_week = timestamp.strftime('%A')
        is_weekday = timestamp.weekday() < 5
        is_weekend = not is_weekday
        hour = timestamp.hour
        minute = timestamp.minute
        
        # Activity and mobility - PRIORITIZE SPEED DATA
        raw_activity = raw_data.get('activity_type', 'STILL')
        speed_kmh = float(raw_data.get('speed', 0.0))
        is_moving = speed_kmh > 1.0
        is_stationary = speed_kmh <= 1.0
        
        # Extract activity state with speed override
        activity_state = self._extract_activity_state(raw_activity, speed_kmh)
        
        # WiFi analysis (soft signals)
        wifi_ssid = raw_data.get('wifi_ssid')
        wifi_analysis = self._analyze_wifi(wifi_ssid)
        
        # Bluetooth analysis (soft signals)
        bluetooth_devices = self._extract_bluetooth_devices(raw_data)
        bluetooth_analysis = self._analyze_bluetooth(bluetooth_devices)
        
        # Location inference (combining multiple signals)
        location_category, location_vector = self._infer_location(
            wifi_analysis=wifi_analysis,
            activity_state=activity_state,
            speed_kmh=speed_kmh,
            raw_location=raw_data.get('location_vector'),
            is_car_connected=bluetooth_analysis['is_car_connected']
        )
        
        # Calendar availability
        calendar_availability = self._extract_calendar_availability(raw_data)
        
        # Device state
        screen_state = self._extract_screen_state(raw_data)
        battery_level = raw_data.get('battery_level')
        battery_state = self._extract_battery_state(battery_level, raw_data.get('is_charging'))
        
        # Data quality assessment
        has_location_data = location_category != LocationCategory.UNKNOWN
        has_calendar_data = calendar_availability != CalendarAvailability.UNKNOWN
        has_battery_data = battery_state != BatteryState.UNKNOWN
        
        confidence_score = self._calculate_confidence_score(
            has_location_data=has_location_data,
            has_calendar_data=has_calendar_data,
            has_battery_data=has_battery_data,
            has_wifi_data=wifi_ssid is not None,
            has_bluetooth_data=len(bluetooth_devices) > 0,
            has_speed_data=speed_kmh >= 0
        )
        
        return ExtractedContext(
            timestamp=timestamp,
            time_of_day=time_of_day,
            day_of_week=day_of_week,
            is_weekday=is_weekday,
            is_weekend=is_weekend,
            hour=hour,
            minute=minute,
            location_category=location_category,
            activity_state=activity_state,
            speed_kmh=speed_kmh,
            is_moving=is_moving,
            is_stationary=is_stationary,
            calendar_availability=calendar_availability,
            screen_state=screen_state,
            battery_state=battery_state,
            battery_level=battery_level,
            wifi_ssid=wifi_ssid,
            is_wifi_connected=wifi_ssid is not None and wifi_ssid != "",
            is_home_wifi=wifi_analysis['is_home'],
            is_campus_wifi=wifi_analysis['is_campus'],
            is_work_wifi=wifi_analysis['is_work'],
            bluetooth_devices=bluetooth_devices,
            is_car_connected=bluetooth_analysis['is_car_connected'],
            is_headphones_connected=bluetooth_analysis['is_headphones_connected'],
            raw_activity_type=raw_activity,
            location_vector=location_vector,
            has_location_data=has_location_data,
            has_calendar_data=has_calendar_data,
            has_battery_data=has_battery_data,
            confidence_score=confidence_score
        )
    
    def _extract_timestamp(self, raw_data: Dict[str, Any]) -> datetime:
        """Extract or create timestamp"""
        timestamp = raw_data.get('timestamp')
        if isinstance(timestamp, str):
            return datetime.fromisoformat(timestamp)
        elif isinstance(timestamp, datetime):
            return timestamp
        else:
            return datetime.utcnow()
    
    def _extract_time_of_day(self, timestamp: datetime) -> TimeOfDay:
        """Categorize time into morning, afternoon, evening, night"""
        hour = timestamp.hour
        if 5 <= hour < 12:
            return TimeOfDay.MORNING
        elif 12 <= hour < 17:
            return TimeOfDay.AFTERNOON
        elif 17 <= hour < 21:
            return TimeOfDay.EVENING
        else:
            return TimeOfDay.NIGHT
    
    def _extract_activity_state(self, raw_activity: str, speed_kmh: float) -> ActivityState:
        """
        Convert raw activity type to normalized activity state.
        CRITICAL: Speed data overrides raw activity type labels.
        """
        # PRIORITY 1: Use real speed data to determine actual activity
        if speed_kmh <= 1.0:
            # Definitely stationary, regardless of what activity_type says
            return ActivityState.STATIONARY
        elif speed_kmh > 1.0 and speed_kmh <= 5.0:
            # Low speed - walking
            return ActivityState.WALKING
        elif speed_kmh > 5.0 and speed_kmh <= 15.0:
            # Medium speed - could be running or cycling
            activity_upper = raw_activity.upper()
            if 'RUNNING' in activity_upper:
                return ActivityState.RUNNING
            elif 'CYCLING' in activity_upper or 'BICYCLE' in activity_upper:
                return ActivityState.CYCLING
            else:
                # Default to walking for medium speeds
                return ActivityState.WALKING
        else:  # speed_kmh > 15.0
            # High speed - definitely in a vehicle
            return ActivityState.TRAVELING
        
        # FALLBACK (should rarely be used): Parse raw activity type
        # This is only reached if speed data is missing or unreliable
        activity_upper = raw_activity.upper()
        
        if activity_upper in ['STILL', 'STATIONARY']:
            return ActivityState.STATIONARY
        elif activity_upper in ['WALKING', 'ON_FOOT']:
            return ActivityState.WALKING
        elif activity_upper in ['IN_VEHICLE', 'DRIVING']:
            return ActivityState.TRAVELING
        elif activity_upper in ['RUNNING']:
            return ActivityState.RUNNING
        elif activity_upper in ['ON_BICYCLE', 'CYCLING']:
            return ActivityState.CYCLING
        else:
            # Default to stationary for unknown activities
            return ActivityState.STATIONARY
    
    def _analyze_wifi(self, wifi_ssid: Optional[str]) -> Dict[str, bool]:
        """Analyze WiFi SSID to infer location type"""
        if not wifi_ssid or wifi_ssid == "":
            return {'is_home': False, 'is_campus': False, 'is_work': False}
        
        wifi_lower = wifi_ssid.lower()
        
        is_home = any(pattern in wifi_lower for pattern in self.HOME_WIFI_PATTERNS)
        is_campus = any(pattern in wifi_lower for pattern in self.CAMPUS_WIFI_PATTERNS)
        is_work = any(pattern in wifi_lower for pattern in self.WORK_WIFI_PATTERNS)
        
        return {
            'is_home': is_home,
            'is_campus': is_campus,
            'is_work': is_work
        }
    
    def _extract_bluetooth_devices(self, raw_data: Dict[str, Any]) -> List[str]:
        """Extract list of connected Bluetooth devices"""
        # Check multiple possible field names
        devices = raw_data.get('bluetooth_devices', [])
        if not devices:
            devices = raw_data.get('connected_devices', [])
        
        # Handle single device case
        if raw_data.get('is_connected_to_car_bluetooth'):
            if 'car' not in [d.lower() for d in devices]:
                devices.append('car_audio')
        
        return devices if isinstance(devices, list) else []
    
    def _analyze_bluetooth(self, devices: List[str]) -> Dict[str, bool]:
        """Analyze Bluetooth devices to infer context"""
        is_car_connected = False
        is_headphones_connected = False
        
        for device in devices:
            device_lower = device.lower()
            
            if any(pattern in device_lower for pattern in self.CAR_BLUETOOTH_PATTERNS):
                is_car_connected = True
            
            if any(pattern in device_lower for pattern in self.HEADPHONE_PATTERNS):
                is_headphones_connected = True
        
        return {
            'is_car_connected': is_car_connected,
            'is_headphones_connected': is_headphones_connected
        }
    
    def _infer_location(
        self,
        wifi_analysis: Dict[str, bool],
        activity_state: ActivityState,
        speed_kmh: float,
        raw_location: Optional[str],
        is_car_connected: bool
    ) -> tuple[LocationCategory, Optional[str]]:
        """
        Infer location category from multiple signals.
        Uses a confidence-based approach with multiple data sources.
        PRIORITY: Real speed data overrides all other signals.
        """
        # Priority 0: ALWAYS check real speed first - this overrides everything
        # If speed is near zero, user is definitely stationary regardless of other signals
        if speed_kmh <= 1.0:
            # User is stationary - check WiFi to determine where
            if wifi_analysis['is_home']:
                return LocationCategory.HOME, 'home'
            elif wifi_analysis['is_campus']:
                return LocationCategory.CAMPUS, 'campus'
            elif wifi_analysis['is_work']:
                return LocationCategory.WORK, 'work'
            # If stationary with explicit location, use it
            elif raw_location:
                location_lower = raw_location.lower()
                if 'home' in location_lower:
                    return LocationCategory.HOME, raw_location
                elif 'campus' in location_lower or 'university' in location_lower:
                    return LocationCategory.CAMPUS, raw_location
                elif 'work' in location_lower or 'office' in location_lower:
                    return LocationCategory.WORK, raw_location
            # Stationary but unknown location
            return LocationCategory.UNKNOWN, 'stationary'
        
        # Priority 1: If speed > 1 km/h, user is moving
        # Check if they're actually traveling (speed > 10 km/h indicates vehicle)
        if speed_kmh > 10.0:
            # Definitely in a vehicle / traveling
            return LocationCategory.COMMUTE, 'commute'
        elif speed_kmh > 1.0 and speed_kmh <= 10.0:
            # Low speed movement - likely walking
            # Could be walking at home, campus, or commuting
            if wifi_analysis['is_home']:
                return LocationCategory.HOME, 'home'
            elif wifi_analysis['is_campus']:
                return LocationCategory.CAMPUS, 'campus'
            elif wifi_analysis['is_work']:
                return LocationCategory.WORK, 'work'
            else:
                # Walking but unknown location
                return LocationCategory.UNKNOWN, 'walking'
        
        # Priority 2: Use explicit location_vector if provided (but speed is still zero)
        if raw_location:
            location_lower = raw_location.lower()
            if 'home' in location_lower:
                return LocationCategory.HOME, raw_location
            elif 'campus' in location_lower or 'university' in location_lower:
                return LocationCategory.CAMPUS, raw_location
            elif 'work' in location_lower or 'office' in location_lower:
                return LocationCategory.WORK, raw_location
            elif 'leaving' in location_lower or 'commute' in location_lower:
                # Only use commute from raw_location if speed indicates movement
                if speed_kmh > 5.0:
                    return LocationCategory.COMMUTE, raw_location
                else:
                    # Ignore commute label if not actually moving
                    return LocationCategory.UNKNOWN, 'stationary_mislabeled'
        
        # Priority 3: WiFi-based inference (fallback when speed is unavailable/zero)
        if wifi_analysis['is_home']:
            return LocationCategory.HOME, 'home'
        elif wifi_analysis['is_campus']:
            return LocationCategory.CAMPUS, 'campus'
        elif wifi_analysis['is_work']:
            return LocationCategory.WORK, 'work'
        
        # Default - unknown location
        return LocationCategory.UNKNOWN, None
    
    def _extract_calendar_availability(self, raw_data: Dict[str, Any]) -> CalendarAvailability:
        """Extract calendar availability from raw data"""
        calendar_status = raw_data.get('calendar_status')
        
        if calendar_status is None:
            return CalendarAvailability.UNKNOWN
        
        status_lower = str(calendar_status).lower()
        
        if status_lower in ['free', 'available']:
            return CalendarAvailability.FREE
        elif status_lower in ['busy', 'occupied', 'meeting']:
            return CalendarAvailability.BUSY
        elif status_lower in ['tentative', 'maybe']:
            return CalendarAvailability.TENTATIVE
        else:
            return CalendarAvailability.UNKNOWN
    
    def _extract_screen_state(self, raw_data: Dict[str, Any]) -> ScreenState:
        """Extract screen state from raw data"""
        screen_on = raw_data.get('screen_on')
        screen_locked = raw_data.get('screen_locked')
        
        if screen_on is None:
            return ScreenState.UNKNOWN
        
        if screen_on and not screen_locked:
            return ScreenState.ACTIVE
        elif screen_on and screen_locked:
            return ScreenState.LOCKED
        else:
            return ScreenState.INACTIVE
    
    def _extract_battery_state(
        self, 
        battery_level: Optional[float], 
        is_charging: Optional[bool]
    ) -> BatteryState:
        """Categorize battery state"""
        if battery_level is None:
            return BatteryState.UNKNOWN
        
        if is_charging:
            return BatteryState.CHARGING
        
        if battery_level > 30:
            return BatteryState.NORMAL
        elif battery_level > 15:
            return BatteryState.LOW
        else:
            return BatteryState.CRITICAL
    
    def _calculate_confidence_score(
        self,
        has_location_data: bool,
        has_calendar_data: bool,
        has_battery_data: bool,
        has_wifi_data: bool,
        has_bluetooth_data: bool,
        has_speed_data: bool
    ) -> float:
        """
        Calculate confidence score based on data completeness.
        Returns value between 0.0 and 1.0.
        """
        # Weighted scoring (some signals are more important)
        weights = {
            'location': 0.25,
            'calendar': 0.15,
            'battery': 0.10,
            'wifi': 0.20,
            'bluetooth': 0.15,
            'speed': 0.15
        }
        
        score = 0.0
        if has_location_data:
            score += weights['location']
        if has_calendar_data:
            score += weights['calendar']
        if has_battery_data:
            score += weights['battery']
        if has_wifi_data:
            score += weights['wifi']
        if has_bluetooth_data:
            score += weights['bluetooth']
        if has_speed_data:
            score += weights['speed']
        
        return round(score, 2)


# Factory function for easy instantiation
def extract_context(raw_data: Dict[str, Any]) -> ExtractedContext:
    """
    Convenience function to extract context from raw data.
    
    Usage:
        raw = {...}  # Raw sensor data
        context = extract_context(raw)
        signature = context.get_context_signature()
    """
    extractor = ContextExtractor()
    return extractor.extract(raw_data)
