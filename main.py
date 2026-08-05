"""Part 107 Ground School - a server-rendered Python (Flask) web app.

All application logic lives in Python. Pages are rendered with Jinja templates;
there is no client-side application JavaScript. The 400-question bank is in
questions.json. Progress is stored on the server, keyed to a per-browser cookie.
"""
import json
import os
import random
import re
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from flask import (Flask, abort, g, jsonify, redirect, render_template, request,
                   session, url_for, Response)
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash
from jinja2 import DictLoader

# ---- Embedded data ----
QUESTIONS_JSON = r'''[
  {
    "b": "Regulations",
    "s": "Accident Reporting",
    "q": "A Part 107 flight causes $600 of damage to a third party's property. Within how many days must you report it to the FAA?",
    "c": [
      "No report required",
      "30 days",
      "10 calendar days",
      "24 hours"
    ],
    "a": 2,
    "e": "Report within 10 calendar days if an accident causes serious injury or at least $500 damage to others' property.",
    "acs": "UA.I.A"
  },
  {
    "b": "Regulations",
    "s": "Accident Reporting",
    "q": "Which outcome requires an FAA accident report under Part 107?",
    "c": [
      "$200 damage to the drone itself",
      "A minor scratch to the operator",
      "A bystander is knocked unconscious",
      "A near-miss with no contact"
    ],
    "a": 2,
    "e": "Reporting is triggered by serious injury or at least $500 damage to others' property.",
    "acs": "UA.I.A"
  },
  {
    "b": "Regulations",
    "s": "Currency",
    "q": "To keep a remote pilot certificate current, the pilot must:",
    "c": [
      "Renew the certificate annually with the FAA",
      "Retake the entire proctored knowledge exam in person every 2 years",
      "Complete free online recurrent training every 24 calendar months",
      "Log 100 flight hours per year"
    ],
    "a": 2,
    "e": "Since 2021 currency is maintained by free online recurrent training every 24 calendar months, with no in-person retest.",
    "acs": "UA.I.C"
  },
  {
    "b": "Regulations",
    "s": "Registration",
    "q": "A drone flown under the limited recreational exception, not Part 107, must be registered when it weighs:",
    "c": [
      "any weight, including under 250 g",
      "0.55 lb (250 g) or more",
      "over 2 lb only",
      "over 5 lb only"
    ],
    "a": 1,
    "e": "Under the recreational exception, registration is required at 0.55 lb (250 g) or more; under Part 107 every drone is registered regardless of weight.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Documents",
    "q": "During a Part 107 operation, the remote PIC must have available for inspection:",
    "c": [
      "Nothing, since a registered drone is automatically exempt from this",
      "Their remote pilot certificate and photo identification",
      "Only a printed paper copy of the full Part 107 regulations",
      "Only the drone's original purchase receipt from the seller"
    ],
    "a": 1,
    "e": "The remote PIC must keep their remote pilot certificate and ID readily accessible during all operations.",
    "acs": "UA.I.A"
  },
  {
    "b": "Regulations",
    "s": "Remote ID",
    "q": "Remote ID requires most drones flown under Part 107 to:",
    "c": [
      "Carry a Mode C transponder like manned aircraft",
      "Broadcast identity, location, and altitude during flight",
      "File a flight plan before each flight",
      "Be painted with the registration number"
    ],
    "a": 1,
    "e": "Remote ID makes the aircraft broadcast its identity, location, and altitude so it can be identified while airborne.",
    "acs": "UA.I.F"
  },
  {
    "b": "Regulations",
    "s": "Supervision",
    "q": "A person without a remote pilot certificate may manipulate the controls only if:",
    "c": [
      "The drone weighs under 250 grams and is therefore exempt from registration",
      "They are over 18 years old and have read the aircraft's flight manual",
      "Under direct supervision of a certificated remote PIC who can take control",
      "They have passed the recreational TRUST test offered to hobby flyers"
    ],
    "a": 2,
    "e": "A non-certificated person may fly only under the direct supervision of a remote PIC able to immediately take over.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Eligibility",
    "q": "The minimum age to be issued a remote pilot certificate is:",
    "c": [
      "18",
      "16",
      "21",
      "14"
    ],
    "a": 1,
    "e": "An applicant must be at least 16 years old to hold a remote pilot certificate.",
    "acs": "UA.I.C"
  },
  {
    "b": "Regulations",
    "s": "Alcohol & Drugs",
    "q": "Part 107 prohibits operating a small UAS within how many hours of consuming alcohol?",
    "c": [
      "8 hours",
      "12 hours",
      "4 hours",
      "24 hours"
    ],
    "a": 0,
    "e": "No operation within 8 hours of alcohol, while impaired, or with a blood alcohol content of 0.04% or greater.",
    "acs": "UA.I.B"
  },
  {
    "b": "Airspace",
    "s": "Class G",
    "q": "In which airspace class may a Part 107 pilot operate without ATC authorization?",
    "c": [
      "Class B",
      "Class C",
      "Class D",
      "Class G"
    ],
    "a": 3,
    "e": "Class G is uncontrolled; controlled airspace (B, C, D, and surface E) requires prior ATC authorization.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Authorization",
    "q": "To fly in Class C airspace under Part 107, a remote pilot must:",
    "c": [
      "Notify the tower by radio before flight",
      "File an IFR flight plan",
      "Obtain prior ATC authorization, usually via LAANC",
      "Simply stay below 200 ft"
    ],
    "a": 2,
    "e": "Operating in controlled airspace requires prior ATC authorization, fastest through LAANC.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "LAANC",
    "q": "LAANC gives Part 107 pilots:",
    "c": [
      "Automatic Remote ID broadcasting through the FAA's national network",
      "A standard aviation weather briefing covering the planned route of flight",
      "Near real-time authorization to fly in controlled airspace up to grid altitudes",
      "Mandatory liability insurance coverage that is required for all Part 107 operations"
    ],
    "a": 2,
    "e": "LAANC grants near-instant authorization up to the maximum altitude shown on the UAS facility grid for that area.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "Class E Surface",
    "q": "Class E airspace extending to the surface (dashed magenta line) for Part 107:",
    "c": [
      "Only applies above 700 ft",
      "Requires ATC authorization before operating",
      "Is uncontrolled and needs no authorization",
      "Restricts manned aircraft only"
    ],
    "a": 1,
    "e": "A Class E surface area is controlled airspace, so it needs authorization just like B, C, and D surface areas.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "TFR",
    "q": "A Temporary Flight Restriction over a stadium during a major game means a Part 107 pilot:",
    "c": [
      "Is exempt from the restriction because the drone weighs so little",
      "May not enter the restricted area without specific authorization",
      "May fly inside it during the hours when no game is being played",
      "May fly inside it freely as long as the aircraft stays under 400 ft"
    ],
    "a": 1,
    "e": "TFRs apply to UAS exactly as to manned aircraft, so entry requires specific FAA authorization.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "NOTAM",
    "q": "Checking NOTAMs before a flight helps a pilot identify:",
    "c": [
      "The drone's battery state",
      "The pilot's certificate expiration",
      "Local traffic ordinances",
      "Temporary hazards, TFRs, and airspace changes"
    ],
    "a": 3,
    "e": "NOTAMs flag temporary conditions such as TFRs, closures, and hazards not printed on charts.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "Speed Limit",
    "q": "The maximum groundspeed of a small UAS under Part 107 is:",
    "c": [
      "87 knots (100 mph)",
      "100 knots",
      "55 knots",
      "No limit applies"
    ],
    "a": 0,
    "e": "Part 107 caps groundspeed at 87 knots, which is 100 mph.",
    "acs": "UA.I.B"
  },
  {
    "b": "Airspace",
    "s": "Grid Values",
    "q": "A UAS Facility Map shows a grid value of 0 over part of a Class D area. This means:",
    "c": [
      "Flight is permanently banned in that grid under all circumstances",
      "No automatic LAANC authorization; a manual request is required",
      "You may fly up to 400 feet there without any further authorization",
      "The area has reverted to uncontrolled Class G airspace for drones"
    ],
    "a": 1,
    "e": "A grid value of 0 means no automatic authorization, so you must request it manually through FAA DroneZone.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "Special Use",
    "q": "A Military Operations Area (MOA) on a chart indicates:",
    "c": [
      "A category of controlled airport that always has an operating tower and radar service",
      "Active military training airspace where pilots should verify status and use caution",
      "Airspace that requires no awareness or coordination from UAS pilots",
      "Permanently prohibited airspace that no aircraft may ever enter"
    ],
    "a": 1,
    "e": "MOAs contain military training; not banned for UAS, but you should check activity status and stay vigilant.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Special Use",
    "q": "Flight in a Prohibited Area such as P-56 over the National Mall is:",
    "c": [
      "Permitted with a LAANC authorization request",
      "Permitted on weekends",
      "Permitted below 400 ft",
      "Not permitted under any circumstances"
    ],
    "a": 3,
    "e": "Prohibited areas are closed to all aircraft including small UAS, with no authorization available.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Symbols",
    "q": "What symbol on a sectional chart indicates Class D airspace?",
    "c": [
      "Solid magenta concentric circles",
      "Solid blue circle",
      "Dashed magenta circle",
      "Dashed blue circle or square"
    ],
    "a": 3,
    "e": "Dashed blue lines enclose Class D airspace around airports with an operating control tower.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Symbols",
    "q": "A dashed magenta line around an airport on a sectional chart indicates:",
    "c": [
      "Class D airspace",
      "Class C inner ring",
      "Class E airspace to the surface",
      "Airport advisory area"
    ],
    "a": 2,
    "e": "Dashed magenta lines depict Class E airspace that extends down to the surface, not just to 700 ft AGL.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Symbols",
    "q": "Class C airspace is depicted on a sectional chart as:",
    "c": [
      "Solid blue square",
      "Solid magenta concentric circles",
      "Dashed blue concentric circles",
      "Dashed magenta square"
    ],
    "a": 1,
    "e": "Two solid magenta rings depict Class C airspace around busier airports served by approach control.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Obstacles",
    "q": "A sectional chart obstacle reads 1549 (549). The parenthetical value is the:",
    "c": [
      "AGL height of the obstacle",
      "Lighting frequency",
      "Distance to the nearest airport",
      "MSL elevation"
    ],
    "a": 0,
    "e": "The parenthetical number is height above ground (AGL); the top number 1549 is the MSL elevation of the top.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Airspace Notation",
    "q": "In a sectional airspace label like SFC to 4000, SFC means:",
    "c": [
      "Sector Flight Ceiling",
      "Secondary Frequency Channel",
      "Standard Flight Corridor",
      "Surface"
    ],
    "a": 3,
    "e": "SFC means the airspace floor begins at ground level rather than a fixed altitude MSL.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Obstacles",
    "q": "An obstacle symbol printed in magenta rather than blue indicates the structure:",
    "c": [
      "Has aviation lighting",
      "Is on military property",
      "Exceeds 1,000 ft AGL",
      "Is in Class C airspace"
    ],
    "a": 2,
    "e": "Obstacles taller than 1,000 ft AGL are printed in magenta as a visual flag for extreme height.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Airspace Notation",
    "q": "Airspace altitude labels like 118 over 40 on a sectional chart are in:",
    "c": [
      "Nautical miles",
      "Feet AGL",
      "Hundreds of feet MSL",
      "Flight levels"
    ],
    "a": 2,
    "e": "Sectional altitude labels are hundreds of feet MSL, so 118 is 11,800 ft and 40 is 4,000 ft.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Navigation",
    "q": "Isogonic lines on a sectional chart connect points of equal:",
    "c": [
      "Magnetic variation from true north",
      "Radio signal strength",
      "Barometric pressure",
      "Terrain elevation"
    ],
    "a": 0,
    "e": "Isogonic lines show where the angle between magnetic and true north (variation) is identical.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Elevation",
    "q": "The bold number inside each lat/lon quadrangle on a sectional chart is the:",
    "c": [
      "Minimum IFR altitude",
      "Maximum Elevation Figure (MEF)",
      "VFR cruising altitude",
      "Traffic pattern altitude"
    ],
    "a": 1,
    "e": "The MEF is the highest known terrain or obstacle in that quadrangle plus a safety buffer, in hundreds of feet.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Special Use",
    "q": "A Military Training Route labeled IR-201 is flown:",
    "c": [
      "Under IFR regardless of weather",
      "Only on weekends",
      "Only above 10,000 ft MSL",
      "Under VFR with visual references required"
    ],
    "a": 0,
    "e": "IR routes are flown by instruments (IFR); VR routes require the pilot to keep visual references.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Symbols",
    "q": "Class B airspace on a sectional chart is depicted as:",
    "c": [
      "Solid magenta concentric circles centered on the primary airport",
      "Dashed blue circles drawn around each nearby airport",
      "Dashed magenta lines surrounding the airport boundary",
      "Solid blue lines forming shelves, often with blue shading"
    ],
    "a": 3,
    "e": "Solid blue lines and shading show the upside-down wedding-cake shelf structure of Class B airspace.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Navigation",
    "q": "A VOR station on a sectional chart appears as:",
    "c": [
      "A magenta triangle pointing toward the nearest airport",
      "A compass rose with a central circle and name flag",
      "A small blue hexagon with the frequency printed inside",
      "A solid blue diamond placed at the station's location"
    ],
    "a": 1,
    "e": "VORs are drawn as a compass rose with a central open circle and an identifying name flag.",
    "acs": "UA.II.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "A METAR reports wind as '27015G25KT'. The gust speed is:",
    "c": [
      "15 knots",
      "25 knots",
      "27 knots",
      "40 knots"
    ],
    "a": 1,
    "e": "G25KT means gusts to 25 knots; 270 is direction and 15 is the steady wind speed.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "In a METAR, 'OVC010' means:",
    "c": [
      "Overcast with 10-mile visibility",
      "Occasional clouds at 1,000 ft",
      "Overcast at 10,000 ft MSL",
      "Overcast at 1,000 ft AGL"
    ],
    "a": 3,
    "e": "Sky layer heights in a METAR are AGL in hundreds of feet, so OVC010 is overcast at 1,000 ft AGL.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "Which sky condition constitutes a ceiling?",
    "c": [
      "Any layer below 3,000 ft AGL",
      "BKN or OVC only",
      "FEW at any altitude",
      "SCT at any altitude"
    ],
    "a": 1,
    "e": "A ceiling is the lowest broken or overcast layer; FEW and SCT coverage do not count as a ceiling.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "The code 'TS' in a METAR present-weather field means:",
    "c": [
      "Temporary snow",
      "Towering stratus",
      "Tropical storm advisory",
      "Thunderstorm"
    ],
    "a": 3,
    "e": "TS is the code for thunderstorm, one of the highest-priority hazards on a report.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "A METAR reports wind as 'VRB03KT'. This means:",
    "c": [
      "Variable direction at 3 knots",
      "Very turbulent 3-knot winds",
      "Visibility cut by 3-knot gusts",
      "Vertical shear at 3 knots"
    ],
    "a": 0,
    "e": "VRB means direction is shifting more than 60 degrees and is reported when speed is 6 knots or less.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "TAF",
    "q": "In a TAF, 'FM1800' followed by new conditions means:",
    "c": [
      "Maximum visibility will be about 1,800 feet",
      "Fog and mist are expected after 1800 Zulu time",
      "From 1800 in the local time of the reporting station",
      "From 1800 UTC, all prior conditions are replaced"
    ],
    "a": 3,
    "e": "FM gives a time in UTC after which all preceding forecast conditions are fully superseded.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "TAF",
    "q": "'TEMPO' in a TAF indicates conditions that:",
    "c": [
      "Apply only during a temperature inversion near the surface",
      "Are permanent for the entire valid period covered by the forecast",
      "Last under 60 minutes each and total less than half the period",
      "Persist for more than half of the forecast period overall"
    ],
    "a": 2,
    "e": "TEMPO marks brief fluctuations, each under an hour, covering less than half the forecast period.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "Density Altitude",
    "q": "Density altitude is defined as:",
    "c": [
      "Indicated altitude corrected for temperature only",
      "Pressure altitude corrected for non-standard temperature",
      "True altitude minus indicated altitude",
      "MSL altitude minus terrain elevation"
    ],
    "a": 1,
    "e": "Density altitude is pressure altitude adjusted for temperature, and it directly governs aircraft performance.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Fog & Clouds",
    "q": "When temperature and dewpoint are within 3 degrees C of each other, expect:",
    "c": [
      "Fog or low cloud formation",
      "Thunderstorm development",
      "Severe turbulence",
      "Icing above 10,000 ft"
    ],
    "a": 0,
    "e": "A small temperature-dewpoint spread means humidity near 100%, so fog or low stratus is likely.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Hazards",
    "q": "The primary hazards near a thunderstorm include:",
    "c": [
      "Slightly reduced visibility with only light, harmless turbulence",
      "Severe turbulence, lightning, hail, and violent wind shear",
      "Reduced radio reception only",
      "Higher humidity and minor GPS drift"
    ],
    "a": 1,
    "e": "Thunderstorms produce extreme turbulence, hail, lightning, and wind shear at once, so avoid them by a wide margin.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Atmosphere",
    "q": "The standard temperature lapse rate in the troposphere is about:",
    "c": [
      "1 degree C per 1,000 ft",
      "2 degrees C per 1,000 ft",
      "2 degrees F per 1,000 ft",
      "4 degrees C per 1,000 ft"
    ],
    "a": 1,
    "e": "The standard lapse rate is roughly 2 degrees C per 1,000 ft, and deviation from it changes density altitude.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Winds Aloft",
    "q": "A winds aloft forecast at 6,000 ft shows '2318-04'. The temperature is:",
    "c": [
      "-18 C",
      "+18 C",
      "+23 C",
      "-4 C"
    ],
    "a": 3,
    "e": "The trailing signed digits are temperature in Celsius, so -04 means minus 4 degrees C at that altitude.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "Fog & Clouds",
    "q": "The dewpoint temperature is:",
    "c": [
      "The average of daily high and low",
      "The exact temperature at which ice crystals begin to form aloft",
      "The temperature to which air must cool to become saturated",
      "The temperature at 500 ft AGL"
    ],
    "a": 2,
    "e": "Dewpoint is the temperature at which air reaches 100% humidity, and cooling below it causes condensation.",
    "acs": "UA.III.B"
  },
  {
    "b": "Operations",
    "s": "Visibility",
    "q": "The minimum flight visibility for Part 107 operations is:",
    "c": [
      "3 statute miles",
      "3 nautical miles",
      "1 statute mile",
      "5 statute miles"
    ],
    "a": 0,
    "e": "Part 107 requires at least 3 statute miles of flight visibility from the control station.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Cloud Clearance",
    "q": "Part 107 cloud clearance requirements are:",
    "c": [
      "1,000 ft below and 1 mile horizontal",
      "500 ft below and 2,000 ft horizontal from clouds",
      "Clear of clouds only",
      "500 ft above and 1,000 ft below"
    ],
    "a": 1,
    "e": "You must stay at least 500 ft below and 2,000 ft horizontally from any cloud.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Right-of-Way",
    "q": "When a manned aircraft approaches, the remote pilot must:",
    "c": [
      "Maintain course since the drone is smaller",
      "Climb above the manned aircraft",
      "Yield the right-of-way and maneuver to avoid it",
      "Hold altitude and broadcast a warning"
    ],
    "a": 2,
    "e": "A small UAS must always yield the right-of-way to all manned aircraft.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "VLOS",
    "q": "Part 107 requires the remote PIC or visual observer to:",
    "c": [
      "Maintain unaided visual line of sight with the aircraft",
      "Use FPV goggles at all times",
      "Keep the drone within 400 ft horizontally",
      "Stay within 1 mile of launch"
    ],
    "a": 0,
    "e": "The aircraft must stay within unaided visual line of sight of the remote PIC or a visual observer.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Night Operations",
    "q": "Under current Part 107 rules, night operations are permitted when:",
    "c": [
      "Never, because operating a small unmanned aircraft at night is prohibited under Part 107",
      "A specific Part 107 waiver is obtained from the FAA for every individual night flight",
      "The flight remains under 100 feet above the ground and stays within 500 feet of the control station",
      "The aircraft has anti-collision lights visible for 3 SM and the pilot has updated training"
    ],
    "a": 3,
    "e": "Night flight is allowed with anti-collision lighting visible for at least 3 statute miles plus the updated knowledge.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Ops Over People",
    "q": "Flying directly over people not part of the operation is:",
    "c": [
      "Always allowed as long as the aircraft remains below 400 feet above the ground",
      "Allowed whenever the aircraft weighs more than 5 lb and carries a parachute",
      "Governed by operational categories based on injury risk, and may be prohibited",
      "Allowed after giving the people a clear verbal warning before each pass overhead"
    ],
    "a": 2,
    "e": "Operations over people fall under Categories 1 through 4, set by the drone's weight and injury potential.",
    "acs": "UA.I.E"
  },
  {
    "b": "Operations",
    "s": "Careless Operation",
    "q": "Operating a small UAS in a careless or reckless manner:",
    "c": [
      "Is allowed in Class G",
      "Applies only to large manned aircraft, never drones",
      "Is prohibited and can lead to certificate action",
      "Is fine if no one is hurt"
    ],
    "a": 2,
    "e": "Careless or reckless operation that endangers people or property is prohibited and can cost your certificate.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "One Aircraft",
    "q": "A remote pilot in command may operate, at one time:",
    "c": [
      "Unlimited with a waiver",
      "Two if both under 250 g",
      "Up to three at once",
      "Only one small UAS"
    ],
    "a": 3,
    "e": "A person may not act as remote PIC of more than one small UAS at the same time.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Preflight",
    "q": "Before each flight, the remote PIC must:",
    "c": [
      "Verify only the battery charge level and skip the rest of the preflight inspection",
      "Inspect the aircraft to confirm it is in a condition for safe operation",
      "File a flight plan with the nearest air traffic control facility",
      "Notify the local police department of the planned flight area"
    ],
    "a": 1,
    "e": "A preflight inspection of the aircraft and systems is required to confirm it is safe to fly.",
    "acs": "UA.V.F"
  },
  {
    "b": "Operations",
    "s": "Over Vehicles",
    "q": "Operating a small UAS from a moving vehicle under Part 107 is:",
    "c": [
      "Always prohibited under all circumstances",
      "Permitted only over sparsely populated areas",
      "Permitted only during nighttime operations",
      "Permitted anywhere as long as you keep it in sight"
    ],
    "a": 1,
    "e": "Operation from a moving vehicle is allowed only over sparsely populated areas, not over people or congested areas.",
    "acs": "UA.I.B"
  },
  {
    "b": "Loading",
    "s": "Payload",
    "q": "Adding payload to a small UAS generally:",
    "c": [
      "Improves stability with no downside",
      "Has no effect under 55 lb",
      "Reduces battery endurance and maneuverability",
      "Increases maximum altitude"
    ],
    "a": 2,
    "e": "Extra weight demands more power to stay airborne, cutting flight time and degrading climb and handling.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Center of Gravity",
    "q": "A payload that shifts the center of gravity out of limits will:",
    "c": [
      "Have no aerodynamic effect as long as it stays under 55 lb total",
      "Improve handling by lowering the aircraft's overall center of mass",
      "Make the aircraft harder to control and possibly unstable",
      "Increase battery life by spreading the load across the airframe"
    ],
    "a": 2,
    "e": "A center of gravity outside limits degrades stability and control and can make the aircraft unflyable.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Density Altitude",
    "q": "On a hot day at high elevation, a multirotor UAS will:",
    "c": [
      "Be unaffected because it is electric",
      "Climb faster",
      "Hover more efficiently in warm air",
      "Produce less lift and need more power to hover"
    ],
    "a": 3,
    "e": "High density altitude means thinner air and less lift, so the aircraft works harder and flies for less time.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Battery",
    "q": "Operating lithium-polymer batteries in cold temperatures usually:",
    "c": [
      "Increases capacity",
      "Permanently prevents the motors from arming at all",
      "Reduces available capacity and flight time",
      "Has no effect"
    ],
    "a": 2,
    "e": "Cold slows battery chemistry, lowering usable capacity and shortening flight time.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Maximum Weight",
    "q": "The maximum total weight including payload for Part 107 operation is:",
    "c": [
      "100 lb",
      "No limit",
      "25 lb",
      "Less than 55 lb"
    ],
    "a": 3,
    "e": "Part 107 covers only small unmanned aircraft weighing less than 55 lb including everything on board.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Wind",
    "q": "Flying into a strong headwind will:",
    "c": [
      "Increase total flight time over the ground",
      "Increase power demand and reduce range and endurance",
      "Improve the GPS accuracy of the aircraft",
      "Have no measurable effect on the battery during the flight"
    ],
    "a": 1,
    "e": "Fighting a headwind makes the motors work harder, draining the battery faster and cutting effective range.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Stability",
    "q": "Stable atmospheric conditions are usually associated with:",
    "c": [
      "Smooth air, layered clouds, and often poorer visibility",
      "Severe wind shear",
      "Rapidly building thunderstorms",
      "Strong turbulence, gusty winds, and towering cumulus clouds"
    ],
    "a": 0,
    "e": "A stable atmosphere resists vertical motion, giving smooth air, stratiform clouds, and often haze.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Weight Distribution",
    "q": "A payload mounted far from the center of a multirotor most likely causes:",
    "c": [
      "A higher top speed because the offset weight streamlines the airframe",
      "Constant attitude correction, raising power use and wear",
      "Improved efficiency since the motors share the load more evenly",
      "Longer flight time as the aircraft needs fewer control inputs"
    ],
    "a": 1,
    "e": "An off-center load forces continuous attitude correction, wasting power and stressing the motors.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Maximum Weight",
    "q": "Exceeding the manufacturer's maximum takeoff weight is likely to:",
    "c": [
      "Improve wind resistance by giving the aircraft more mass",
      "Raise the service ceiling the aircraft can safely reach",
      "Degrade climb performance and may prevent safe flight",
      "Extend battery life by spreading the load more evenly"
    ],
    "a": 2,
    "e": "Overloading past the manufacturer's limit cuts climb capability and can make safe flight impossible.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Regulations",
    "s": "Waivers",
    "q": "A Part 107 Certificate of Waiver allows a remote pilot to:",
    "c": [
      "Skip the initial knowledge test as long as another certificated pilot is present",
      "Ignore any Part 107 operating rule at the pilot's own discretion during the course of the flight",
      "Deviate from certain operating rules when the FAA finds the operation can be conducted safely",
      "Operate the aircraft without registering it or marking it with a registration number"
    ],
    "a": 2,
    "e": "A waiver permits deviation from specific waivable rules only when the FAA is satisfied the operation can be done safely.",
    "acs": "UA.I.D"
  },
  {
    "b": "Regulations",
    "s": "Authorization vs Waiver",
    "q": "Entering controlled airspace needs an airspace authorization. To deviate from an operating rule such as flying beyond visual line of sight, you need:",
    "c": [
      "A medical certificate",
      "A waiver",
      "A second authorization",
      "A TFR"
    ],
    "a": 1,
    "e": "Airspace access is granted by an authorization, while permission to deviate from an operating rule comes from a waiver.",
    "acs": "UA.I.D"
  },
  {
    "b": "Regulations",
    "s": "Visual Observer",
    "q": "If an operation uses a visual observer, that person must:",
    "c": [
      "Be able to see the aircraft and stay in communication with the remote PIC",
      "Take over flying the controls whenever the remote pilot becomes busy",
      "Remain at least 1 statute mile away from the aircraft at all times",
      "Hold a separate remote pilot certificate issued under Part 107 of the regulations"
    ],
    "a": 0,
    "e": "A visual observer keeps the aircraft in sight and stays in communication with the remote PIC to support see-and-avoid.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Carriage of Property",
    "q": "Transporting another person's property by drone for compensation under Part 107 is:",
    "c": [
      "Always prohibited, because Part 107 does not permit carrying property for hire",
      "Allowed only above 400 feet so the aircraft stays clear of people below",
      "Allowed across state lines without any limit on the total takeoff weight",
      "Allowed only within one state, under 55 lb total, with no hazardous materials"
    ],
    "a": 3,
    "e": "Property for hire may be carried only within one state, under 55 lb total, and never hazardous materials.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Hazardous Materials",
    "q": "A small UAS operated under Part 107 may carry:",
    "c": [
      "Hazardous materials if under 5 lb",
      "Cargo, but never hazardous materials",
      "Any cargo without restriction",
      "Hazardous materials with a waiver only"
    ],
    "a": 1,
    "e": "Part 107 prohibits carrying hazardous materials regardless of weight.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Physical Condition",
    "q": "Under Part 107, an FAA medical certificate is:",
    "c": [
      "Required every 24 calendar months, the same interval as the recurrent knowledge training",
      "Not required, but you may not fly with a condition that would interfere with safe operation",
      "Required for any small unmanned aircraft weighing more than 5 lb, and renewed before each flight",
      "Required only for night flight or operations conducted in controlled airspace near airports"
    ],
    "a": 1,
    "e": "No medical certificate is required, but you may not fly with a condition that impairs safe operation.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "English Requirement",
    "q": "To be eligible for a remote pilot certificate, an applicant must:",
    "c": [
      "Own an aircraft that is registered with the FAA",
      "Already hold a private pilot certificate",
      "Be a United States citizen or lawful permanent resident",
      "Be able to read, speak, write, and understand English"
    ],
    "a": 3,
    "e": "English proficiency in reading, speaking, writing, and understanding is an eligibility requirement for the certificate.",
    "acs": "UA.I.C"
  },
  {
    "b": "Regulations",
    "s": "FAA Inspection",
    "q": "When asked by the FAA, the remote PIC must:",
    "c": [
      "Refer the inspector to the drone manufacturer for any compliance questions",
      "Provide a written flight plan filed in advance with the local control tower",
      "Decline to cooperate or answer questions until the FAA produces a court-issued warrant",
      "Present the remote pilot certificate and allow inspection of the aircraft and records"
    ],
    "a": 3,
    "e": "On request, the remote PIC must show the certificate and allow FAA inspection of the aircraft and records.",
    "acs": "UA.I.A"
  },
  {
    "b": "Regulations",
    "s": "Registration Marking",
    "q": "The registration number issued to a small unmanned aircraft must be:",
    "c": [
      "Painted in red letters at least 3 inches tall",
      "Broadcast over radio before flight",
      "Kept only in the pilot's records",
      "Marked on the exterior of the aircraft and legible"
    ],
    "a": 3,
    "e": "The registration number must be displayed on the aircraft's exterior surface and be readable.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Registration Validity",
    "q": "Registration for a small UAS is valid for:",
    "c": [
      "The life of the aircraft",
      "3 years",
      "5 years",
      "1 year"
    ],
    "a": 1,
    "e": "Small unmanned aircraft registration must be renewed every 3 years.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Dropping Objects",
    "q": "Dropping an object from a small UAS in flight is:",
    "c": [
      "Allowed if reasonable precautions are taken to avoid injury or damage",
      "Always prohibited under Part 107 regardless of the precautions that are taken",
      "Allowed only after obtaining a specific waiver from the FAA for each operation",
      "Allowed only over open water and well clear of any vessels or swimmers below"
    ],
    "a": 0,
    "e": "You may drop an object as long as reasonable precautions prevent it from creating an undue hazard to people or property.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Preflight",
    "q": "Before each Part 107 flight, the remote PIC must assess:",
    "c": [
      "The pilot's certificate expiration date and registration number",
      "Only the battery charge level, since the aircraft software checks everything else",
      "The operating environment, including airspace, weather, and obstacles",
      "The current resale value of the aircraft and its installed payload"
    ],
    "a": 2,
    "e": "A preflight assessment of local airspace, weather, terrain, and obstacles is required before every operation.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Other Laws",
    "q": "Complying with Part 107:",
    "c": [
      "Overrides all conflicting state and local laws automatically in every case",
      "Does not exempt you from state or local privacy and trespass laws",
      "Means you do not have to be aware of any local rules",
      "Replaces the need to get permission from the landowner first"
    ],
    "a": 1,
    "e": "Federal Part 107 governs the airspace operation but does not preempt state or local privacy, trespass, and similar laws.",
    "acs": "UA.I.A"
  },
  {
    "b": "Regulations",
    "s": "Single Remote PIC",
    "q": "For every Part 107 operation there must be:",
    "c": [
      "An air traffic controller assigned to monitor the entire operation",
      "A designated remote PIC who is the final authority for that flight",
      "A licensed aircraft mechanic on site for the duration of the flight",
      "At least two certificated remote pilots present at the control station"
    ],
    "a": 1,
    "e": "Each operation must have one remote PIC who is directly responsible for and the final authority over that flight.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "TRUST",
    "q": "The TRUST test is intended for:",
    "c": [
      "Air traffic controllers who manage drone traffic near airports",
      "All Part 107 applicants, in place of the knowledge test",
      "Manned aircraft pilots seeking an additional drone rating",
      "Recreational flyers, not Part 107 commercial operators"
    ],
    "a": 3,
    "e": "TRUST satisfies the recreational flyer requirement and is separate from the Part 107 knowledge test.",
    "acs": "UA.I.A"
  },
  {
    "b": "Regulations",
    "s": "Knowledge Test",
    "q": "The Part 107 initial knowledge test is taken:",
    "c": [
      "Online from home using a webcam while a remote proctor monitors the session live",
      "At an FAA-approved testing center with government-issued photo identification",
      "At any towered airport after scheduling an appointment with the control tower staff",
      "By mail, by returning a completed answer sheet to the FAA within sixty days"
    ],
    "a": 1,
    "e": "The initial knowledge test is proctored at an FAA-approved testing center and requires valid photo identification.",
    "acs": "UA.I.C"
  },
  {
    "b": "Regulations",
    "s": "Certificate Application",
    "q": "After passing the knowledge test, an applicant obtains the certificate by:",
    "c": [
      "Paying a one-time fee directly to the drone manufacturer",
      "Registering the drone, which automatically issues the certificate",
      "Applying through IACRA and completing TSA security vetting",
      "Waiting two years for the FAA to mail it automatically"
    ],
    "a": 2,
    "e": "The applicant files through IACRA, and after TSA vetting receives a temporary then a permanent remote pilot certificate.",
    "acs": "UA.I.C"
  },
  {
    "b": "Regulations",
    "s": "Waiver Limits",
    "q": "Which of the following cannot be waived under Part 107?",
    "c": [
      "The prohibition on carrying hazardous materials",
      "Flight over people",
      "Beyond visual line of sight",
      "Operation of the control station from a moving vehicle"
    ],
    "a": 0,
    "e": "Many operating rules are waivable, but the ban on carrying hazardous materials is not.",
    "acs": "UA.I.D"
  },
  {
    "b": "Regulations",
    "s": "Remote ID",
    "q": "A drone that does not broadcast standard Remote ID on its own can still comply by:",
    "c": [
      "Keeping the aircraft below 200 feet above the ground at all times",
      "Attaching a Remote ID broadcast module, or flying only within a FRIA",
      "Registering the same aircraft twice under two different owners",
      "Flying only at night with anti-collision lighting visible for 3 statute miles"
    ],
    "a": 1,
    "e": "Comply via a standard Remote ID drone, a broadcast module, or flying inside a FRIA.",
    "acs": "UA.I.F"
  },
  {
    "b": "Regulations",
    "s": "FRIA",
    "q": "A FAA-Recognized Identification Area (FRIA) is:",
    "c": [
      "A defined area where drones without Remote ID may be flown",
      "A type of controlled airspace requiring ATC authorization",
      "A permanent no-fly zone closed to all unmanned aircraft",
      "A pilot certification level above the basic remote certificate"
    ],
    "a": 0,
    "e": "A FRIA is an approved location where aircraft without Remote ID broadcast capability may still be flown.",
    "acs": "UA.I.F"
  },
  {
    "b": "Regulations",
    "s": "Registration Scope",
    "q": "Under Part 107, registration is handled so that:",
    "c": [
      "One number covers an entire fleet",
      "Registration is not required",
      "Only the pilot is registered",
      "Each aircraft is registered individually"
    ],
    "a": 3,
    "e": "Part 107 requires each unmanned aircraft to be registered individually, each with its own registration.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Falsification",
    "q": "Falsifying any record or report required under Part 107 is:",
    "c": [
      "Prohibited and grounds for certificate action or penalties",
      "Permitted for minor clerical errors that are later corrected",
      "Only a concern for manned pilots, not remote pilots",
      "Allowed as long as the falsification was not intentional"
    ],
    "a": 0,
    "e": "Making a fraudulent or false record or report is prohibited and can result in suspension, revocation, or penalties.",
    "acs": "UA.I.A"
  },
  {
    "b": "Regulations",
    "s": "Currency",
    "q": "Part 107 recurrent training is:",
    "c": [
      "Required only for pilots who intend to fly at night or over people",
      "A paid in-person exam taken at an FAA-approved testing center",
      "Required every year and renewed before the prior one lapses",
      "Completed online for free, with no proctored retest"
    ],
    "a": 3,
    "e": "Currency is kept through free online recurrent training every 24 calendar months, with no proctored retest.",
    "acs": "UA.I.C"
  },
  {
    "b": "Regulations",
    "s": "Certificate Validity",
    "q": "A remote pilot certificate itself:",
    "c": [
      "Expires every 2 years and must be reissued only after a proctored retest at a center",
      "Must be renewed every year by submitting a new application to the FAA",
      "Does not expire, but the holder must stay current with recurrent training",
      "Is valid for life with no further requirements once it is issued"
    ],
    "a": 2,
    "e": "The certificate does not expire, but the pilot must complete recurrent training to remain eligible to operate.",
    "acs": "UA.I.C"
  },
  {
    "b": "Regulations",
    "s": "Recreational Exception",
    "q": "A person flying purely for recreation may instead operate under:",
    "c": [
      "Part 107 rules only, with no recreational option available to anyone",
      "A manned-aircraft pilot certificate issued by the FAA after a checkride",
      "The recreational flyer exception, with its own separate rules",
      "No rules at all, since recreation is completely exempt from oversight"
    ],
    "a": 2,
    "e": "Recreational flying uses the limited recreational exception, which has its own rules separate from Part 107.",
    "acs": "UA.I.A"
  },
  {
    "b": "Regulations",
    "s": "Accident Reporting",
    "q": "A reportable Part 107 accident must be reported to:",
    "c": [
      "The manufacturer",
      "The FAA, within 10 calendar days",
      "No one",
      "The local police department only, in person"
    ],
    "a": 1,
    "e": "A qualifying accident is reported to the FAA within 10 calendar days of the operation.",
    "acs": "UA.I.A"
  },
  {
    "b": "Regulations",
    "s": "Operating Limitations",
    "q": "Core Part 107 operating limits include a maximum altitude of 400 ft AGL, a maximum groundspeed of 87 knots, and:",
    "c": [
      "A minimum flight visibility of 3 statute miles",
      "A maximum flight time of 30 minutes",
      "A maximum weight of 25 lb",
      "A minimum altitude of 100 ft"
    ],
    "a": 0,
    "e": "Among the core limits are 400 ft AGL, 87 knots, and at least 3 statute miles of flight visibility from the control station.",
    "acs": "UA.I.B"
  },
  {
    "b": "Airspace",
    "s": "Class B",
    "q": "Class B airspace surrounds the busiest airports, and for a Part 107 pilot it:",
    "c": [
      "Is uncontrolled",
      "Is open to drones below 400 ft without authorization",
      "Requires ATC authorization before any operation",
      "Allows flight only at night"
    ],
    "a": 2,
    "e": "Class B is controlled airspace, so any operation inside it requires prior ATC authorization.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Class D",
    "q": "Class D airspace typically extends from the surface up to about:",
    "c": [
      "10,000 ft MSL across the charted area",
      "700 ft AGL above the airport field",
      "18,000 ft MSL, the floor of Class A airspace",
      "2,500 ft above the airport elevation"
    ],
    "a": 3,
    "e": "Class D normally reaches roughly 2,500 ft above the airport and exists only while the control tower is operating.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Class C",
    "q": "A standard Class C airspace is shaped as:",
    "c": [
      "Three concentric magenta rings of increasing radius around the airport",
      "A square box about 4 NM on each side centered on the primary airport",
      "A single circular ring with a 10 NM radius extending up from the surface",
      "An inner surface core near 5 NM and an outer shelf near 10 NM"
    ],
    "a": 3,
    "e": "Class C has an inner core to the surface near 5 NM and a raised outer shelf near 10 NM.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Class E",
    "q": "Away from airports, controlled Class E airspace most commonly begins at:",
    "c": [
      "10,000 ft MSL",
      "Only above 18,000 ft",
      "The surface everywhere",
      "700 or 1,200 ft AGL"
    ],
    "a": 3,
    "e": "Class E usually starts at 1,200 ft AGL, dropping to 700 ft AGL beneath the magenta vignette near airports.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Class A",
    "q": "Class A airspace begins at:",
    "c": [
      "14,500 ft MSL",
      "18,000 ft MSL",
      "The surface at major airports",
      "10,000 ft MSL"
    ],
    "a": 1,
    "e": "Class A runs from 18,000 ft MSL up to FL600, far above any Part 107 operation.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Class G",
    "q": "Class G airspace is:",
    "c": [
      "Controlled airspace that always begins at 1,200 ft above the ground",
      "Uncontrolled airspace where Part 107 needs no ATC authorization",
      "Controlled airspace that requires ATC authorization to enter",
      "Airspace that is restricted to manned aircraft only"
    ],
    "a": 1,
    "e": "Class G is uncontrolled, so flight there needs no ATC authorization, though all other Part 107 rules still apply.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Restricted Area",
    "q": "A Restricted Area such as R-2503 indicates airspace that:",
    "c": [
      "Is permanently closed to every aircraft, military and civil alike, at all altitudes",
      "Is uncontrolled airspace that any aircraft may enter without prior coordination",
      "Contains hazards like artillery or missile testing and may be entered only with permission",
      "Is reserved exclusively for unmanned aircraft operating under Part 107 rules"
    ],
    "a": 2,
    "e": "Restricted areas contain hazards to flight and may be entered only with permission from the controlling agency.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Warning Area",
    "q": "A Warning Area is generally located:",
    "c": [
      "At smaller airports that have no control towers",
      "Over open water, starting 3 NM off the coast",
      "Inside Class B only",
      "Over major cities"
    ],
    "a": 1,
    "e": "Warning areas extend outward from the coast over international waters and contain activity hazardous to aircraft.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Alert Area",
    "q": "An Alert Area on a sectional chart warns of:",
    "c": [
      "A permanent flight ban that applies to all aircraft at all times",
      "Live weapons testing conducted by the military at scheduled times",
      "A noise-sensitive zone where engine power should be reduced",
      "A high volume of pilot training or unusual aerial activity"
    ],
    "a": 3,
    "e": "Alert areas warn of heavy training or unusual activity, where all pilots share responsibility for vigilance.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "National Security Area",
    "q": "A National Security Area (NSA) asks pilots to:",
    "c": [
      "Obtain a waiver in every case",
      "Voluntarily avoid flying in the area",
      "Treat it as prohibited airspace",
      "File a flight plan"
    ],
    "a": 1,
    "e": "Pilots are requested to voluntarily avoid an NSA, and flight there can be temporarily prohibited by NOTAM.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Stadium TFR",
    "q": "The standing sporting-event TFR over large stadiums applies:",
    "c": [
      "To manned aircraft only, with no restriction placed on small drones",
      "Only during the playing of the national anthem and the opening ceremony before kickoff",
      "Within 3 NM up to 3,000 ft AGL, from one hour before to one hour after the event",
      "Within 1 NM of the stadium at any altitude for the entire duration of the day"
    ],
    "a": 2,
    "e": "The stadium TFR covers a 3 NM radius to 3,000 ft AGL, starting one hour before and ending one hour after the event.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "VIP TFR",
    "q": "A TFR protecting the movement of the President:",
    "c": [
      "Can be safely ignored by small unmanned aircraft as long as they fly below 400 feet",
      "Applies only to aircraft operating above 10,000 feet mean sea level",
      "Is published only after the protected movement has already taken place",
      "Creates a no-fly area drones may not enter without specific authorization"
    ],
    "a": 3,
    "e": "VIP movement TFRs create restricted airspace that small UAS must not enter without specific authorization.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Non-Towered Airport",
    "q": "Operating in Class G near an airport without a control tower, you:",
    "c": [
      "Need no authorization but must stay clear of the traffic pattern and not interfere",
      "Must contact the nearest air traffic control tower for clearance before launch",
      "Need prior ATC authorization just as you would inside controlled airspace",
      "May fly through the traffic pattern freely as long as you yield to manned aircraft"
    ],
    "a": 0,
    "e": "Class G needs no authorization, but you must avoid the traffic pattern and never interfere with manned aircraft.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "Authorization Source",
    "q": "When automatic LAANC is not available, airspace authorization is requested through:",
    "c": [
      "The local police department",
      "A flight service station by phone",
      "The drone manufacturer",
      "The FAA DroneZone portal"
    ],
    "a": 3,
    "e": "If LAANC cannot approve a request automatically, authorization is requested manually through FAA DroneZone.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "UAS Facility Map",
    "q": "The altitude printed in a UAS Facility Map grid square is:",
    "c": [
      "The airport elevation measured at the center of the nearest field",
      "The maximum altitude for automatic LAANC authorization there",
      "A mandatory minimum altitude that drones must climb to before flying",
      "The floor of the overlying Class E airspace in that grid square"
    ],
    "a": 1,
    "e": "The grid value is the ceiling up to which LAANC will automatically approve operations in that square.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "Sectional Chart",
    "q": "For planning a Part 107 flight, the most appropriate chart is the:",
    "c": [
      "Airport diagram only",
      "IFR high-altitude en route chart",
      "Surface analysis chart",
      "VFR sectional chart"
    ],
    "a": 3,
    "e": "The VFR sectional shows airspace, obstacles, and terrain at the scale a small UAS operation needs.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Time",
    "q": "Aviation weather reports and NOTAMs state time in:",
    "c": [
      "The aircraft's local time at its current position",
      "Coordinated Universal Time, marked with a Z",
      "Local time only, set to the reporting station",
      "Eastern time, regardless of the station location"
    ],
    "a": 1,
    "e": "Aviation uses Coordinated Universal Time, written with a Z, so reports are unambiguous across time zones.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "Controlled Firing Area",
    "q": "A Controlled Firing Area (CFA) is:",
    "c": [
      "A type of Class C airspace surrounding certain military training installations",
      "Marked on the sectional in solid red as airspace that is closed to all traffic",
      "Always active and prohibited to civil aircraft, including small unmanned aircraft",
      "Not charted, because its activity stops whenever an aircraft approaches"
    ],
    "a": 3,
    "e": "CFAs are not depicted because their activity ceases as soon as an aircraft is detected nearby.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Authorization Scope",
    "q": "If your planned path clips a corner of Class D airspace, you:",
    "c": [
      "May pass through briefly without authorization",
      "Need a waiver instead",
      "Still need authorization for that airspace",
      "Only need to stay under 200 ft"
    ],
    "a": 2,
    "e": "Any entry into controlled airspace, even briefly, requires prior authorization.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "NOTAM",
    "q": "Current NOTAMs and TFRs are best checked before flight:",
    "c": [
      "By word of mouth from other pilots flying in the same general area",
      "The day after the flight, once the official records have been updated",
      "From the drone manufacturer's customer support line shortly before each planned flight",
      "Through an official FAA source such as a preflight briefing or NOTAM search"
    ],
    "a": 3,
    "e": "NOTAMs and TFRs change often, so verify them from an official FAA source close to flight time.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "Class E Surface",
    "q": "A dashed magenta boundary at an airport tells a Part 107 pilot that:",
    "c": [
      "It is Class B airspace requiring a specific clearance before any operation",
      "The surrounding area is uncontrolled Class G up to 1,200 feet above the ground",
      "Flight is prohibited within the boundary unless a specific waiver has been issued",
      "Class E reaches the surface there and authorization is required"
    ],
    "a": 3,
    "e": "A dashed magenta line marks Class E to the surface, which is controlled and requires authorization.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Equipment",
    "q": "A small UAS operating in authorized Class C airspace:",
    "c": [
      "Must file an IFR flight plan before entering the airspace",
      "Does not need a transponder, but does need the authorization",
      "Must carry a Mode C transponder and reply to interrogations",
      "Must squawk 7500 on the transponder for the duration of the flight"
    ],
    "a": 1,
    "e": "Small UAS are not required to carry transponders, but they still need ATC authorization to enter Class C.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "Special Flight Rules",
    "q": "Drone flight in the inner Flight Restricted Zone of the Washington, DC area is:",
    "c": [
      "Allowed only at night",
      "The same as any Class G",
      "Effectively closed without special approval",
      "Completely unrestricted anywhere under 400 ft"
    ],
    "a": 2,
    "e": "The DC Flight Restricted Zone bars drone flight without special authorization.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Floor and Ceiling",
    "q": "On a sectional, an airspace tag reading 40 over SFC means the airspace:",
    "c": [
      "Extends from the surface up to 4,000 ft MSL",
      "Tops out at 400 ft",
      "Is 40 NM wide",
      "Requires a 40-knot minimum speed at all times"
    ],
    "a": 0,
    "e": "The top number is the ceiling in hundreds of feet MSL, and SFC means it starts at the surface.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Prohibited Area",
    "q": "A Prohibited Area, such as the one over the White House, is:",
    "c": [
      "Closed to all aircraft, with no authorization available",
      "A military training area that is active only during daytime hours",
      "Open to flight once a LAANC authorization has been obtained",
      "Open to drones below 400 feet above the ground at any time"
    ],
    "a": 0,
    "e": "Prohibited areas are closed to all aircraft including small UAS, and no authorization is available.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Wildlife Areas",
    "q": "Charted wildlife refuges and similar areas remind pilots to:",
    "c": [
      "Treat the area as Class B airspace that requires an ATC clearance to enter",
      "Always obtain a Temporary Flight Restriction before operating nearby",
      "Land immediately and report their position to the managing federal agency",
      "Avoid disturbing wildlife and maintain higher altitudes where requested"
    ],
    "a": 3,
    "e": "Charts request that pilots avoid low flight over wildlife refuges to limit disturbance.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Yielding",
    "q": "When a manned aircraft is operating nearby in any airspace, the remote pilot must:",
    "c": [
      "Yield the right of way and maneuver clear",
      "Continue if below 400 ft",
      "Climb to be more visible",
      "Simply hold its current position and altitude"
    ],
    "a": 0,
    "e": "Small UAS always yield the right of way to manned aircraft, regardless of airspace class.",
    "acs": "UA.I.B"
  },
  {
    "b": "Charts",
    "s": "Airport Symbols",
    "q": "On a sectional chart, an airport shown in blue rather than magenta indicates it:",
    "c": [
      "Is private",
      "Has an operating control tower",
      "Has no runway lighting",
      "Is closed"
    ],
    "a": 1,
    "e": "Blue airport symbols have an operating control tower, while magenta airports do not.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Obstacles",
    "q": "An obstacle drawn with a small star or radiating lines at its top indicates the obstacle is:",
    "c": [
      "Lighted",
      "Under construction",
      "Temporary",
      "Privately owned"
    ],
    "a": 0,
    "e": "Radiating lines or a star at an obstacle symbol mean it is equipped with obstruction lighting.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Obstacles",
    "q": "Two obstacle symbols joined together on a chart represent:",
    "c": [
      "A power plant",
      "An airport",
      "A group of obstacles",
      "A single very tall tower"
    ],
    "a": 2,
    "e": "A joined pair of obstacle symbols depicts a group of obstructions close together.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Airport Data",
    "q": "In an airport data block on a sectional, the number that gives field elevation is the:",
    "c": [
      "Runway heading",
      "Elevation in feet above mean sea level",
      "Tower frequency",
      "Traffic pattern altitude"
    ],
    "a": 1,
    "e": "The airport data block lists field elevation in feet MSL along with runway and frequency information.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Visual Checkpoint",
    "q": "A magenta flag symbol on a sectional chart marks a:",
    "c": [
      "Seaplane base where takeoffs and landings on the water are conducted",
      "Prohibited area that bars all aircraft from entering it",
      "Visual checkpoint used for reporting position or navigation",
      "Wind turbine farm marked as an obstruction to flight"
    ],
    "a": 2,
    "e": "A magenta flag denotes a visual checkpoint, a prominent landmark pilots use for position reporting.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Navigation",
    "q": "On a sectional chart, a VORTAC is shown as:",
    "c": [
      "A small magenta flag placed at the reporting point",
      "A dashed blue square drawn around the navigation facility and its service area",
      "A plain magenta circle with no compass rose or added markings",
      "A VOR compass rose symbol with added markings for the TACAN component"
    ],
    "a": 3,
    "e": "A VORTAC combines a VOR with military TACAN, drawn as the VOR symbol with extra corner markings.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Navigation",
    "q": "The compass rose drawn around a VOR on a sectional is oriented to:",
    "c": [
      "True north",
      "The nearest runway",
      "Magnetic north",
      "Grid north"
    ],
    "a": 2,
    "e": "The VOR compass rose is aligned to magnetic north, which is why charts also show magnetic variation.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airways",
    "q": "The light blue lines radiating between navigation aids on a sectional represent:",
    "c": [
      "State boundaries",
      "The outer edges of nearby restricted areas",
      "Victor airways used by other aircraft",
      "Power lines"
    ],
    "a": 2,
    "e": "Victor airways are charted routes between VORs, and knowing them helps anticipate where manned traffic flies.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Terrain",
    "q": "The graduated color tints on a sectional chart show:",
    "c": [
      "Airspace classes, with each class shown in a different color",
      "Population density, with cities shown in the darkest shades",
      "Terrain elevation, with higher ground in darker shades",
      "Weather patterns expected across the region during the day"
    ],
    "a": 2,
    "e": "Elevation tints shade higher terrain in progressively darker colors so pilots can judge ground height at a glance.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Special Use",
    "q": "Detailed information about restricted and prohibited areas on a sectional is found:",
    "c": [
      "Only in the legend",
      "In a tabulation along the chart border",
      "Nowhere; it must be memorized",
      "On a separate weather chart"
    ],
    "a": 1,
    "e": "Special use airspace details such as altitudes and times are listed in a tabulation block on the chart margin.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Obstacles",
    "q": "A power transmission line that may be a hazard to low flight is charted as:",
    "c": [
      "A line with small tower symbols where it is a known hazard",
      "A dashed magenta circle centered on the midpoint of the line",
      "A magenta flag symbol placed at each end of the transmission line",
      "A solid blue band running along the full length of the wires"
    ],
    "a": 0,
    "e": "Charted power lines and their support towers warn of wires that are a serious hazard to low-altitude flight.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Elevation",
    "q": "The Maximum Elevation Figure in a chart quadrangle is found by taking the highest obstacle or terrain and:",
    "c": [
      "Subtracting the nearest airport's published field elevation",
      "Converting the height from feet into nautical miles",
      "Adding a buffer, then rounding up to the next hundred feet",
      "Dividing the result by two to allow for a safety margin"
    ],
    "a": 2,
    "e": "The MEF is the highest terrain or obstacle in the quadrangle plus a buffer, in hundreds of feet MSL.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Airport Symbols",
    "q": "A small letter R inside an airport symbol indicates the airport is:",
    "c": [
      "A seaplane base usable only by float-equipped aircraft",
      "Private, with restricted or prior-permission use",
      "Closed permanently and no longer available for landing",
      "A military base restricted to government aircraft only"
    ],
    "a": 1,
    "e": "An R marks a private airport that requires prior permission, so it is not available for general public use.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Obstacles",
    "q": "When two numbers are printed at an obstacle, such as 2049 with 449 below in parentheses, the top number is the:",
    "c": [
      "The straight-line distance to the nearest airport",
      "Height above ground",
      "Height of the top above mean sea level",
      "Obstacle lighting code"
    ],
    "a": 2,
    "e": "The top figure is the top of the obstacle in feet MSL, while the parenthetical figure is its height above ground.",
    "acs": "UA.II.B"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "In the METAR group 'KDEN 121753Z', the 121753Z means the report was taken on:",
    "c": [
      "The 12th day at 1753 Coordinated Universal Time",
      "The 12th of the month at 1753 local clock time",
      "December 17th at the reporting station",
      "12 minutes past 1753 in the local time of the station"
    ],
    "a": 0,
    "e": "The first two digits are the day of the month and the next four are the time in Coordinated Universal Time.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "In a METAR, the group 'A2992' is the:",
    "c": [
      "A ground visibility of exactly 29.92 statute miles",
      "Temperature of 29 degrees",
      "Wind speed of 92 knots",
      "Altimeter setting of 29.92 inches of mercury"
    ],
    "a": 3,
    "e": "An A followed by four digits is the altimeter setting in inches of mercury, here 29.92.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "In a METAR the group '18/12' reports the:",
    "c": [
      "Visibility 18 and 12",
      "Time 1812",
      "Wind 180 at 12",
      "Temperature 18 C and dewpoint 12 C"
    ],
    "a": 3,
    "e": "The slash pair is temperature over dewpoint in Celsius, and a small spread points to possible fog or low cloud.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "A METAR visibility group of '1/2SM' means visibility is:",
    "c": [
      "12 miles",
      "One or two miles",
      "One half statute mile",
      "Half a nautical mile"
    ],
    "a": 2,
    "e": "Visibility in a METAR is given in statute miles, so 1/2SM is one half of a statute mile.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "In a METAR present-weather field, 'BR' stands for:",
    "c": [
      "Mist",
      "Broken clouds",
      "Brief rain",
      "Breezy"
    ],
    "a": 0,
    "e": "BR is the code for mist, a reduction in visibility from suspended water droplets, distinct from FG which is fog.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "Sky Cover",
    "q": "On a weather report, the difference between SCT and BKN is that:",
    "c": [
      "SCT always reports clouds higher than BKN does at the same site",
      "SCT is 3 to 4 eighths of cloud cover and BKN is 5 to 7 eighths",
      "BKN means no clouds at all while SCT means a fully overcast sky",
      "They mean the same thing and are used interchangeably in reports"
    ],
    "a": 1,
    "e": "Scattered is 3 to 4 eighths of sky cover, while broken is 5 to 7 eighths and counts as a ceiling.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "Reports",
    "q": "The main difference between a METAR and a TAF is that:",
    "c": [
      "A METAR reports observed conditions, while a TAF is a forecast",
      "A METAR is always a forecast, while a TAF is the observed weather",
      "Both are observations",
      "Both are forecasts"
    ],
    "a": 0,
    "e": "A METAR is an observation of current conditions, while a TAF forecasts conditions for an airport area.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "TAF",
    "q": "A TAF typically forecasts conditions for an area around an airport of about:",
    "c": [
      "5 statute miles",
      "1 mile",
      "50 miles",
      "The whole state"
    ],
    "a": 0,
    "e": "A TAF applies to roughly a 5 statute mile radius around the airport for its valid period.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "TAF",
    "q": "In a TAF, 'PROB30' indicates:",
    "c": [
      "A steady wind of about 30 knots at the surface",
      "A forecast visibility of about 30 statute miles ahead",
      "A 30 percent probability of the stated conditions",
      "Conditions that will last for about 30 minutes"
    ],
    "a": 2,
    "e": "PROB30 marks a 30 percent chance of the associated weather during that part of the forecast.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "TAF",
    "q": "In a TAF, 'BECMG' is used when conditions are:",
    "c": [
      "Improving instantly the moment the change begins",
      "Brief, lasting under an hour within the forecast",
      "Gradually changing over a period to a new steady state",
      "Not expected to be forecast at any point in the period"
    ],
    "a": 2,
    "e": "BECMG marks a gradual change to new conditions that are then expected to persist.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "Fronts",
    "q": "A fast-moving cold front is most likely to bring:",
    "c": [
      "Long periods of light, steady, widespread drizzle",
      "No noticeable change in the weather at all",
      "Gradually lowering ceilings and steady rain spread over a full day",
      "Gusty winds, showers or thunderstorms, and a quick clearing"
    ],
    "a": 3,
    "e": "Cold fronts lift warm air quickly, often producing gusty winds and showers or thunderstorms followed by clearing.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Fronts",
    "q": "A warm front typically produces:",
    "c": [
      "Sudden violent thunderstorms followed quickly by gusty clearing winds",
      "Immediate clearing with rising ceilings and improving surface visibility",
      "Gradually lowering ceilings, widespread cloud, and steady precipitation",
      "Strong downslope winds and rapidly falling temperatures behind the front"
    ],
    "a": 2,
    "e": "Warm air rising gently over cooler air gives a warm front its broad cloud, lowering ceilings, and steady precipitation.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Inversion",
    "q": "A temperature inversion is a layer where temperature:",
    "c": [
      "Drops below freezing only at the very top of the affected layer",
      "Increases with altitude, often trapping haze and smooth stable air",
      "Stays exactly constant from the surface up through the entire layer",
      "Decreases with altitude faster than the standard lapse rate does"
    ],
    "a": 1,
    "e": "In an inversion temperature rises with height, creating a stable layer that traps moisture, haze, and pollutants.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Wind Shear",
    "q": "Low-level wind shear is dangerous to a small UAS because it:",
    "c": [
      "Causes sudden changes in wind speed or direction that can upset control",
      "Improves battery life by reducing the power the motors must draw",
      "Only affects manned aircraft operating well above 10,000 feet mean sea level",
      "Has no measurable effect on multirotor aircraft near the ground"
    ],
    "a": 0,
    "e": "Wind shear is a rapid change in wind over a short distance that can suddenly destabilize a small aircraft.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Microburst",
    "q": "A microburst associated with a thunderstorm produces:",
    "c": [
      "A steady tailwind that helps the aircraft return to the pilot",
      "Calm, stable air directly beneath the base of the storm cell",
      "A powerful localized downdraft with dangerous shifting winds",
      "Improved visibility only, with no effect on the surface wind"
    ],
    "a": 2,
    "e": "A microburst is an intense, short-lived downdraft whose outflow creates severe and rapidly changing winds.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Pressure Systems",
    "q": "In the Northern Hemisphere, a high-pressure system is generally associated with:",
    "c": [
      "Tornado formation along a fast-moving squall line",
      "Descending air, fair weather, and lighter winds",
      "Rising air, building clouds, and frequent storms",
      "Continuous heavy rain over a wide area for several days"
    ],
    "a": 1,
    "e": "High pressure brings sinking air and fair weather; low pressure brings clouds and precipitation.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Standard Atmosphere",
    "q": "Standard sea-level conditions are:",
    "c": [
      "15 degrees C and 29.92 inches of mercury",
      "0 degrees C and 30.00 inches",
      "20 degrees C and 28.00 inches",
      "25 degrees C and 29.92 inches"
    ],
    "a": 0,
    "e": "The standard atmosphere uses 15 degrees C and 29.92 inches of mercury at sea level as the reference.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Density Altitude",
    "q": "Density altitude increases, hurting performance, when conditions are:",
    "c": [
      "Cold, dry air at a low-elevation field",
      "Cold and humid with a steady surface breeze",
      "Low elevation paired with cool, dry air at the surface",
      "High temperature, high humidity, and high elevation"
    ],
    "a": 3,
    "e": "Heat, humidity, and altitude all thin the air, raising density altitude and reducing lift and power.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Turbulence",
    "q": "Mechanical turbulence near the ground is commonly caused by:",
    "c": [
      "Calm, stable air with very little surface wind",
      "A temperature inversion acting entirely on its own",
      "Wind flowing around buildings, terrain, and obstacles",
      "Unusually high visibility on a clear and perfectly calm day"
    ],
    "a": 2,
    "e": "Air flowing over and around obstructions breaks into eddies, producing mechanical turbulence near the surface.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Local Winds",
    "q": "A sea breeze along a coastline on a sunny afternoon generally flows:",
    "c": [
      "From the cooler water toward the warmer land",
      "Only at night, after the land has fully cooled",
      "Straight down from the clouds toward the surface",
      "From the warmer land outward toward the open sea"
    ],
    "a": 0,
    "e": "Daytime heating of land draws cooler air in from the water, creating an onshore sea breeze.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Convection",
    "q": "On a hot day, convective currents over different surfaces tend to cause:",
    "c": [
      "Perfectly smooth air",
      "Reduced battery temperature",
      "Bumpy, turbulent air at low altitude",
      "Stable layered clouds only"
    ],
    "a": 2,
    "e": "Uneven heating creates rising and sinking columns of air, giving low-altitude flights a bumpy, turbulent ride.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Fog",
    "q": "Advection fog forms when:",
    "c": [
      "Strong winds mix dry air down",
      "Warm, moist air moves over a cooler surface",
      "A cold front passes quickly",
      "Ground cools on a clear, calm night"
    ],
    "a": 1,
    "e": "Advection fog forms as warm moist air moves horizontally over a cooler surface and cools to its dewpoint.",
    "acs": "UA.III.B"
  },
  {
    "b": "Operations",
    "s": "VLOS",
    "q": "Visual line of sight under Part 107 must be maintained:",
    "c": [
      "With unaided vision, though corrective lenses are allowed",
      "Using binoculars or a spotting scope to extend the visual range farther out",
      "Only during takeoff and landing, not during cruise",
      "Through the aircraft's onboard camera and video feed"
    ],
    "a": 0,
    "e": "VLOS must be kept with natural vision, with glasses or contacts permitted, but not binoculars or a camera feed.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "First-Person View",
    "q": "Flying with first-person-view goggles is allowed under Part 107 only if:",
    "c": [
      "The entire flight is conducted at night using anti-collision lighting visible for 3 SM",
      "The aircraft being flown weighs less than 250 grams with its battery",
      "The remote pilot keeps the aircraft below 200 feet above the ground",
      "A visual observer maintains unaided visual line of sight with the aircraft"
    ],
    "a": 3,
    "e": "FPV is permitted as long as a visual observer keeps the aircraft within unaided line of sight at all times.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Visual Observer",
    "q": "When a visual observer is used, the remote PIC and observer must:",
    "c": [
      "Stand at least 100 ft apart",
      "Maintain effective communication at all times",
      "Always use two entirely separate control stations",
      "Each fly a different aircraft"
    ],
    "a": 1,
    "e": "The remote PIC and visual observer must keep effective communication so see-and-avoid responsibilities are coordinated.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Over People Cat 1",
    "q": "Category 1 operations over people generally require the aircraft to:",
    "c": [
      "Weigh under 55 lb, the same limit that applies to all Part 107 flights",
      "Weigh 0.55 lb or less and have no parts that can lacerate skin",
      "Carry a current airworthiness certificate issued under part 21",
      "Carry a deployable parachute system tested by an accredited lab"
    ],
    "a": 1,
    "e": "Category 1 allows flight over people for aircraft 0.55 lb or lighter with no exposed parts that could lacerate skin.",
    "acs": "UA.I.E"
  },
  {
    "b": "Operations",
    "s": "Over People",
    "q": "Whether you may fly over people not involved in the operation depends on:",
    "c": [
      "The color and visibility of the aircraft against the sky during the operation",
      "The time of day, since flights over people are permitted only during civil daylight hours",
      "The operational category, which is based on the aircraft and its injury potential",
      "The total number of flight hours the remote pilot has logged as pilot in command"
    ],
    "a": 2,
    "e": "Operations over people are sorted into Categories 1 through 4 based on weight and the risk of injury.",
    "acs": "UA.I.E"
  },
  {
    "b": "Operations",
    "s": "Open-Air Assembly",
    "q": "Sustained flight over an open-air assembly of people requires the aircraft to:",
    "c": [
      "Fly only at civil twilight, when fewer people are present below",
      "Meet an operational category and broadcast Remote ID",
      "Stay under 100 feet above the assembly at all times",
      "Weigh over 5 lb so it can carry the required safety equipment"
    ],
    "a": 1,
    "e": "Flight over open-air assemblies requires meeting Category 1 through 3 conditions and broadcasting Remote ID.",
    "acs": "UA.I.E"
  },
  {
    "b": "Operations",
    "s": "In-Flight Emergency",
    "q": "During an in-flight emergency, the remote PIC may:",
    "c": [
      "Never deviate from any rule, since the rules apply even during emergencies",
      "Hand the aircraft to a nearby bystander to share the workload temporarily",
      "Deviate from Part 107 rules to the extent needed to meet the emergency",
      "Ignore manned traffic in the area because the emergency takes priority"
    ],
    "a": 2,
    "e": "In an in-flight emergency the remote PIC may deviate from any Part 107 rule to the extent required to handle it.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Transfer of Control",
    "q": "Handing off control of a small UAS during a flight is:",
    "c": [
      "Never permitted, because only one person may touch the controls per flight",
      "Allowed between certificated remote PICs who coordinate the transfer",
      "Allowed to any bystander as long as the remote PIC stays within arm's reach",
      "Allowed only while the aircraft is on the ground and the motors are stopped"
    ],
    "a": 1,
    "e": "Control may pass between qualified pilots if the handoff is coordinated and one PIC stays responsible.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Hazardous Attitudes",
    "q": "The thought I can do anything is an example of which hazardous attitude?",
    "c": [
      "Resignation",
      "Macho",
      "Anti-authority",
      "Impulsivity"
    ],
    "a": 1,
    "e": "The macho attitude shows up as overconfidence, and its antidote is taking it slow because reckless chances are foolish.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Hazardous Attitudes",
    "q": "A pilot who thinks rules are for other people is showing:",
    "c": [
      "Anti-authority",
      "Resignation",
      "Macho",
      "Invulnerability"
    ],
    "a": 0,
    "e": "The anti-authority attitude resists rules, and its antidote is recognizing that the rules are usually right.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Hazardous Attitudes",
    "q": "Believing an accident will not happen to me is the hazardous attitude of:",
    "c": [
      "Impulsivity",
      "Resignation",
      "Invulnerability",
      "Macho"
    ],
    "a": 2,
    "e": "Invulnerability is thinking it cannot happen to you; the antidote is accepting that it can.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Hazardous Attitudes",
    "q": "Acting on the first idea that comes to mind without thinking is:",
    "c": [
      "Resignation",
      "Impulsivity",
      "Macho",
      "Anti-authority"
    ],
    "a": 1,
    "e": "Impulsivity is doing something quickly without analysis, and its antidote is to think first, then act.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Hazardous Attitudes",
    "q": "Feeling that what happens is out of your hands reflects:",
    "c": [
      "Invulnerability",
      "Anti-authority",
      "Macho",
      "Resignation"
    ],
    "a": 3,
    "e": "Resignation is giving up a sense of control, and its antidote is recognizing that you can make a difference.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "ADM",
    "q": "Aeronautical decision making (ADM) is best described as:",
    "c": [
      "Following the most experienced pilot's advice without question",
      "Reacting to problems only after they actually occur during the flight itself",
      "A systematic approach to consistently choosing the best course of action",
      "Memorizing the regulations so they can be recited from memory"
    ],
    "a": 2,
    "e": "ADM is a structured way of evaluating information and risks to consistently make sound flight decisions.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Risk Management",
    "q": "The PAVE checklist helps a pilot assess risk in the categories of:",
    "c": [
      "Preflight, Approach, Verify, Execute",
      "Power, Altitude, Visibility, Endurance",
      "People, Area, Visibility, Equipment",
      "Pilot, Aircraft, enVironment, and External pressures"
    ],
    "a": 3,
    "e": "PAVE breaks risk into Pilot, Aircraft, enVironment, and External pressures so hazards can be identified before flight.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Fitness to Fly",
    "q": "The IMSAFE checklist is used to evaluate:",
    "c": [
      "The aircraft's mechanical condition",
      "The pilot's own fitness to fly",
      "The airspace authorization",
      "The weather forecast"
    ],
    "a": 1,
    "e": "IMSAFE checks Illness, Medication, Stress, Alcohol, Fatigue, and Emotion to judge whether the pilot is fit to fly.",
    "acs": "UA.V.E"
  },
  {
    "b": "Operations",
    "s": "CRM",
    "q": "Crew resource management for a Part 107 crew mainly involves:",
    "c": [
      "Assigning all tasks to the visual observer",
      "Effectively using all available people, information, and equipment",
      "Letting the single most senior person present decide absolutely everything",
      "Avoiding any communication during flight"
    ],
    "a": 1,
    "e": "CRM is the effective use of all available resources, people, information, and equipment, to operate safely.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Fatigue",
    "q": "Fatigue affects a remote pilot by:",
    "c": [
      "Having no effect on drone operations",
      "Slowing reaction time and degrading judgment",
      "Only mattering for manned pilots",
      "Improving focus over long flights"
    ],
    "a": 1,
    "e": "Fatigue slows reaction time and impairs decision making, so a tired pilot should not fly.",
    "acs": "UA.V.E"
  },
  {
    "b": "Operations",
    "s": "Stress",
    "q": "High stress during an operation is likely to:",
    "c": [
      "Sharpen all senses indefinitely",
      "Have no effect if the pilot is certificated",
      "Narrow attention and impair decision making",
      "Only affect new pilots"
    ],
    "a": 2,
    "e": "Stress can narrow attention and degrade judgment, which is why managing it is part of safe operation.",
    "acs": "UA.V.E"
  },
  {
    "b": "Operations",
    "s": "Lost Link",
    "q": "A sound preflight plan should include what to do if:",
    "c": [
      "The control link or GPS is lost during flight",
      "The weather is perfect",
      "The battery happens to already be fully charged",
      "A bystander asks a question"
    ],
    "a": 0,
    "e": "Planning for a lost link or lost GPS, such as a return-to-home behavior, reduces the chance of a fly-away.",
    "acs": "UA.V.C"
  },
  {
    "b": "Operations",
    "s": "Preflight",
    "q": "A preflight check of the control station should confirm:",
    "c": [
      "A solid control link, sufficient battery, and current firmware",
      "Only that the propellers spin freely when the motors are armed",
      "The current resale value of the aircraft on the used market",
      "The remote pilot's certificate number and its expiration date"
    ],
    "a": 0,
    "e": "Verifying the control link, power, and firmware before flight helps prevent in-flight failures.",
    "acs": "UA.V.F"
  },
  {
    "b": "Operations",
    "s": "Maintenance",
    "q": "Keeping a small UAS in a condition for safe operation is:",
    "c": [
      "The responsibility of the remote PIC",
      "Only the manufacturer's concern",
      "Required only for aircraft over 5 lb",
      "Optional for hobby flights"
    ],
    "a": 0,
    "e": "The remote PIC is responsible for determining the aircraft is in a safe condition before each flight.",
    "acs": "UA.V.F"
  },
  {
    "b": "Operations",
    "s": "Crew Briefing",
    "q": "Before a multi-person operation, the remote PIC should:",
    "c": [
      "Assign all decisions to the observer",
      "Brief everyone on roles, the plan, and emergency procedures",
      "Wait until well after the launch to begin assigning any roles",
      "Keep the plan private to avoid confusion"
    ],
    "a": 1,
    "e": "A preflight briefing of roles and emergency procedures keeps the crew coordinated and reduces errors.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Bystander Safety",
    "q": "If uninvolved people enter the operating area during a flight, the remote PIC should:",
    "c": [
      "Descend and hold a low hover directly above the people until they leave",
      "Continue the operation as planned since they entered the area voluntarily",
      "Maneuver to keep the aircraft from flying over them, or land if needed",
      "Speed up to finish the planned flight quickly before they move any closer"
    ],
    "a": 2,
    "e": "The remote PIC must avoid flying over people not part of the operation, repositioning or landing as needed.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Night Lighting",
    "q": "For night operations, the required anti-collision lighting must:",
    "c": [
      "Be a steady white light mounted so that it is visible only from directly above the aircraft",
      "Be visible for at least 3 statute miles and flash at a rate to prevent collision",
      "Face downward toward the ground so that it does not distract other nearby aircraft",
      "Be visible for at least 1 statute mile and remain steadily illuminated throughout the flight"
    ],
    "a": 1,
    "e": "Night flight requires anti-collision lights visible for at least 3 statute miles, flashing to help prevent a collision.",
    "acs": "UA.II.B"
  },
  {
    "b": "Operations",
    "s": "Night Training",
    "q": "To fly at night under the current rules, a remote pilot must:",
    "c": [
      "Obtain a specific waiver from the FAA before every individual night flight",
      "Hold an instrument rating in addition to the remote pilot certificate",
      "Have completed the updated recurrent training covering night operations",
      "Be directly supervised by a manned-aircraft pilot during the operation"
    ],
    "a": 2,
    "e": "Night operations require the lighting plus the updated training that now includes night content.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Over People",
    "q": "Without meeting a special category, a remote pilot may fly over a person who is:",
    "c": [
      "Directly participating in the operation, or under a covered structure or inside a stationary covered vehicle",
      "Any bystander on the ground, provided the aircraft remains below 400 feet and within the pilot's visual line of sight",
      "Anyone who has given the remote pilot clear verbal consent to be overflown during the operation",
      "A spectator at a sporting event or concert as long as the flight is brief and stays overhead"
    ],
    "a": 0,
    "e": "Without a category, you may fly only over participants or people shielded by a covered structure or stationary covered vehicle.",
    "acs": "UA.I.E"
  },
  {
    "b": "Operations",
    "s": "Visibility Reference",
    "q": "The minimum 3 statute miles of visibility under Part 107 is measured:",
    "c": [
      "From the control station",
      "At the destination airport",
      "From the highest obstacle",
      "At cloud base"
    ],
    "a": 0,
    "e": "Flight visibility of at least 3 statute miles is judged from the control station location.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Site Selection",
    "q": "Launching a drone from private property generally requires:",
    "c": [
      "A TFR",
      "Permission from the property owner or manager",
      "Nothing, since the airspace is federal",
      "An airspace authorization"
    ],
    "a": 1,
    "e": "Federal rules govern the airspace, but you still need permission to launch from or land on private property.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Error Chain",
    "q": "Most accidents result from:",
    "c": [
      "Always a single mechanical failure",
      "Only weather",
      "A chain of small errors rather than a single cause",
      "Pure bad luck that simply cannot be managed at all ever"
    ],
    "a": 2,
    "e": "Accidents usually grow from a chain of small errors, and breaking any link in the chain can prevent the outcome.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Careless Operation",
    "q": "Operating a small UAS so as to endanger people or property is:",
    "c": [
      "Prohibited as careless or reckless operation",
      "Allowed in Class G",
      "Only an issue for manned aircraft",
      "Allowed if no one is hurt"
    ],
    "a": 0,
    "e": "Careless or reckless operation that endangers life or property is prohibited and can lead to certificate action.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Personal Minimums",
    "q": "Setting personal minimums for wind, visibility, and experience helps a pilot:",
    "c": [
      "Make consistent go or no-go decisions and avoid pressing into unsafe conditions",
      "Skip the preflight assessment when conditions appear calm and clear",
      "Disregard the regulations whenever personal experience suggests it is safe",
      "Legally fly in any weather condition as long as the aircraft stays within line of sight"
    ],
    "a": 0,
    "e": "Personal minimums give a clear line for go or no-go decisions before external pressures push toward an unsafe flight.",
    "acs": "UA.V.D"
  },
  {
    "b": "Loading",
    "s": "Total Weight",
    "q": "The total weight that matters for Part 107 limits and performance includes:",
    "c": [
      "Only the battery, since it is the single heaviest component on board",
      "The aircraft plus battery, payload, and anything else on board",
      "The airframe by itself, not counting the battery, payload, or mounting hardware",
      "Only the payload that is mounted for the specific mission"
    ],
    "a": 1,
    "e": "Maximum weight covers everything on board, so payload and battery count toward the under-55-lb limit and performance.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Humidity",
    "q": "High humidity affects multirotor performance by:",
    "c": [
      "Having no effect",
      "Cooling the motors and giving them noticeably more power",
      "Lowering air density, which reduces lift and thrust",
      "Increasing lift"
    ],
    "a": 2,
    "e": "Moist air is less dense than dry air, so high humidity raises density altitude and reduces lift and thrust.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Battery Health",
    "q": "As a lithium battery ages through many charge cycles, its capacity:",
    "c": [
      "Slowly increases the more it is used",
      "Gradually decreases, shortening flight time",
      "Only really matters during the hot summer months",
      "Stays exactly constant for its whole life"
    ],
    "a": 1,
    "e": "Battery capacity fades with age and cycles, so an older pack delivers less flight time than when it was new.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Voltage Sag",
    "q": "Under a heavy load or at low charge, battery voltage sag can:",
    "c": [
      "Extend total flight time as the pack discharges more slowly",
      "Improve the climb rate because the motors run cooler then",
      "Reduce available power and trigger a low-power landing",
      "Increase the aircraft's top speed by drawing extra current"
    ],
    "a": 2,
    "e": "Voltage sag lowers available power, which can force a return or landing before the pack is fully empty.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Propellers",
    "q": "Operating with a chipped or damaged propeller is likely to:",
    "c": [
      "Improve efficiency by letting air pass more smoothly over it",
      "Increase battery life because the lighter blade draws less power",
      "Cause vibration and reduced lift, and may lead to failure",
      "Have no effect at all as long as you stay below 400 feet AGL"
    ],
    "a": 2,
    "e": "A damaged propeller upsets balance and lift, causing vibration and risking an in-flight failure.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Wind",
    "q": "A strong tailwind while the aircraft is returning will:",
    "c": [
      "Have no effect on the approach as long as the aircraft stays within visual line of sight",
      "Increase groundspeed and can lengthen the distance needed to stop or descend on target",
      "Slow the aircraft over the ground and shorten the distance needed for the approach",
      "Reduce battery drain to nearly zero because the wind pushes the aircraft home for free"
    ],
    "a": 1,
    "e": "A tailwind raises groundspeed, so the aircraft covers more ground and needs more room to stop or land accurately.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Gusts",
    "q": "Gusty wind conditions reduce a small UAS pilot's safety margin because they:",
    "c": [
      "Lower the density altitude, which makes the motors work noticeably harder",
      "Make the aircraft easier to fly by holding it steady against the breeze",
      "Demand more control input and power, leaving less margin for error",
      "Improve GPS accuracy because the receiver locks onto more satellites"
    ],
    "a": 2,
    "e": "Gusts force constant correction and higher power use, cutting into the reserve available to handle a problem.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Payload Drag",
    "q": "Mounting a bulky payload that disturbs airflow will most likely:",
    "c": [
      "Add drag, increasing power use and reducing endurance",
      "Improve the long-term health of the flight battery",
      "Reduce drag and noticeably save battery power in cruise",
      "Increase the service ceiling that the aircraft can safely reach"
    ],
    "a": 0,
    "e": "A payload that disrupts airflow adds drag, so the motors work harder and flight time drops.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Maneuverability",
    "q": "Adding weight to a small UAS generally:",
    "c": [
      "Reduces maneuverability and lengthens the distance to stop or change direction",
      "Increases the maximum altitude the aircraft can safely reach",
      "Improves agility and noticeably shortens the distance needed to stop or change direction",
      "Has no measurable effect on how the aircraft handles during flight"
    ],
    "a": 0,
    "e": "More weight increases inertia, so the aircraft is slower to respond and needs more room to maneuver.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Center of Gravity",
    "q": "A center of gravity that is too far aft tends to make an aircraft:",
    "c": [
      "Immune to wind",
      "Unable to take off",
      "Less stable and harder to control",
      "More stable but slower"
    ],
    "a": 2,
    "e": "An aft center of gravity reduces stability, making the aircraft more sensitive and harder to control.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Center of Gravity",
    "q": "A center of gravity that is too far forward tends to make an aircraft:",
    "c": [
      "More stable but heavier on the controls and harder to maneuver",
      "Noticeably lighter on the controls and faster in level forward flight",
      "Unstable and twitchy, overreacting to even small control inputs in flight",
      "Unaffected in handling because the flight controller compensates automatically"
    ],
    "a": 0,
    "e": "A forward center of gravity adds stability but makes the aircraft feel heavy and less responsive to maneuver.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Manufacturer Limits",
    "q": "The best source for a specific drone's maximum payload and balance limits is:",
    "c": [
      "Another pilot's guess",
      "The sectional chart",
      "A general public internet discussion forum thread",
      "The manufacturer's operating documentation"
    ],
    "a": 3,
    "e": "The manufacturer's documentation gives the tested weight and balance limits for that specific aircraft.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Endurance Planning",
    "q": "When carrying a payload, a pilot should plan for:",
    "c": [
      "Longer flight time than usual because of the added mass",
      "No change at all to endurance, since the motors compensate",
      "Reduced flight time and a battery reserve for landing",
      "Unlimited hover time as long as the wind stays calm"
    ],
    "a": 2,
    "e": "Payload cuts endurance, so plan a shorter mission and keep a battery reserve to land safely.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Charts",
    "s": "Airport Data",
    "q": "In an airport data block, CT followed by a frequency such as 118.3 indicates the:",
    "c": [
      "Field elevation",
      "Control tower frequency",
      "Runway length",
      "Pattern altitude"
    ],
    "a": 1,
    "e": "CT with a frequency is the control tower frequency for that airport.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Airport Symbols",
    "q": "Small tick marks around an airport circle on a sectional indicate:",
    "c": [
      "A military field",
      "A seaplane base",
      "The airport is closed",
      "Fuel is available"
    ],
    "a": 3,
    "e": "Tick marks around the airport circle show fuel services are available.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Airport Data",
    "q": "In an airport data block, the runway length is shown:",
    "c": [
      "In hundreds of feet, so 53 means about 5,300 ft",
      "In nautical miles measured from end to end of the runway",
      "As the radio frequency used by the airport control tower",
      "As a magnetic heading pointing along the main runway"
    ],
    "a": 0,
    "e": "Runway length appears in hundreds of feet, so 53 is roughly 5,300 ft.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Terrain",
    "q": "Contour lines and color tints on a sectional help a pilot judge:",
    "c": [
      "The class of airspace overlying each section of the charted region",
      "Rising terrain that could reduce clearance above the ground",
      "Prevailing wind direction and speed at the surface during daylight hours",
      "Magnetic variation between true north and magnetic north across the area"
    ],
    "a": 1,
    "e": "Contours and tints show terrain relief so you keep clearance above rising ground.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Special Use",
    "q": "A Military Training Route labeled VR-1207 is flown:",
    "c": [
      "Only at altitudes above 18,000 feet within positive control airspace",
      "Always under instrument flight rules regardless of the weather",
      "Under visual flight rules, with the pilot keeping visual references",
      "Only at night when other military traffic is not operating"
    ],
    "a": 2,
    "e": "VR routes are flown under visual rules, while IR routes are flown by instruments.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Navigation",
    "q": "Magnetic variation is the difference between:",
    "c": [
      "Indicated and true altitude",
      "Pressure and density altitude",
      "Two VOR radials",
      "True north and magnetic north"
    ],
    "a": 3,
    "e": "Variation is the angle between true and magnetic north, shown by isogonic lines.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Symbols",
    "q": "Class B floors and ceilings on a sectional are shown as:",
    "c": [
      "Single values in feet above ground level printed just inside the boundary",
      "Magenta vignettes that fade outward from the center of the airspace",
      "Dashed lines only, with the altitudes listed in a separate chart legend",
      "Pairs of numbers in hundreds of feet MSL along each segment"
    ],
    "a": 3,
    "e": "Each Class B segment lists its ceiling over its floor in hundreds of feet MSL.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airport Symbols",
    "q": "Larger airports on a sectional are drawn:",
    "c": [
      "As a single solid dot regardless of how many runways they have",
      "With their actual runway layout rather than a simple circle",
      "With a dashed boundary line showing the edge of the airport property",
      "As a magenta flag symbol placed at the center of the field"
    ],
    "a": 1,
    "e": "Busier airports are depicted with their true runway pattern instead of a plain circle.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Special Use",
    "q": "The times and altitudes of a charted restricted area are found:",
    "c": [
      "On the compass rose drawn around the nearest navigation aid",
      "In the special use airspace tabulation in the chart margin",
      "In the terrain shading that surrounds the restricted area",
      "In the airport data block next to the primary airport symbol"
    ],
    "a": 1,
    "e": "Restricted area details are listed in a tabulation along the chart margin.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Obstacles",
    "q": "An obstacle that is reported but not yet verified is charted with:",
    "c": [
      "A bold red circle",
      "A dashed symbol",
      "A magenta flag",
      "No symbol at all"
    ],
    "a": 1,
    "e": "Unverified obstacles use a dashed symbol to show their position or height is uncertain.",
    "acs": "UA.II.B"
  },
  {
    "b": "Loading",
    "s": "Performance",
    "q": "Compared with a cool sea-level day, a hot day at high elevation makes a multirotor:",
    "c": [
      "Climb faster because the warmer air is less dense",
      "Use less battery thanks to the reduced air resistance",
      "Carry more payload than it could at sea level",
      "Climb more slowly and hover with less margin"
    ],
    "a": 3,
    "e": "Heat and altitude thin the air, cutting lift so it climbs and hovers with less margin.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Battery",
    "q": "A practical way to protect flight time in cold weather is to:",
    "c": [
      "Keep batteries warm until just before launch",
      "Fly with a nearly empty pack",
      "Add extra payload",
      "Warm up the propellers thoroughly before takeoff"
    ],
    "a": 0,
    "e": "Cold cuts battery capacity, so keeping packs warm until launch preserves flight time.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Center of Gravity",
    "q": "Mounting a camera well forward of a drone's center will:",
    "c": [
      "Shift the center of gravity and change how it handles",
      "Have no measurable effect on the aircraft's balance in flight",
      "Improve battery life by streamlining the airframe",
      "Raise the legal maximum takeoff weight for the aircraft"
    ],
    "a": 0,
    "e": "An off-center payload moves the center of gravity and alters handling.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Wind",
    "q": "Planning a flight in steady 20 knot winds, a pilot should expect:",
    "c": [
      "Improved hover stability as the steady wind holds the aircraft in place",
      "Longer flight time since the wind helps push the aircraft along its route",
      "Higher power use, shorter flight time, and less control margin",
      "No measurable change in endurance because the wind averages out over time"
    ],
    "a": 2,
    "e": "Wind forces constant correction and higher power draw, cutting endurance and margin.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Total Weight",
    "q": "A drone rated to 4 lb is fitted with a 1.5 lb payload, reaching 5 lb. The pilot should:",
    "c": [
      "Treat it as overloaded and expect degraded performance",
      "Ignore the manufacturer rating, which is only a suggestion",
      "Expect longer flight time from the added battery mass",
      "Assume performance is unchanged since 5 lb is still light"
    ],
    "a": 0,
    "e": "Exceeding the rated weight degrades climb and handling, so stay within the limit.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Propellers",
    "q": "A nicked or bent propeller found during preflight should be:",
    "c": [
      "Flown until it fails",
      "Replaced before flight",
      "Ignored below 400 ft",
      "Sanded smooth and reused indefinitely"
    ],
    "a": 1,
    "e": "A damaged propeller upsets balance and lift, risking vibration and failure, so replace it.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Manufacturer Limits",
    "q": "The most reliable source for a drone's maximum payload is:",
    "c": [
      "Another pilot's advice",
      "The manufacturer's specifications",
      "Trial and error in flight",
      "An estimate from its size"
    ],
    "a": 1,
    "e": "The manufacturer's specifications give the tested payload and balance limits.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Stability",
    "q": "In stable air, a pilot can generally expect:",
    "c": [
      "Strong turbulence with rapid up and down drafts throughout",
      "Building cumulus clouds and developing afternoon thunderstorms",
      "Smooth flight, though visibility may be reduced by haze",
      "Frequent wind shear and sharp gusts close to the surface"
    ],
    "a": 2,
    "e": "Stable air gives smooth flight but often hazy, reduced visibility.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Density Altitude",
    "q": "High density altitude is worst for a heavily loaded drone because it:",
    "c": [
      "Has no effect on multirotors, which rely on direct motor thrust",
      "Improves climb because the thinner air offers less resistance",
      "Adds reduced lift to the extra weight, hurting climb most",
      "Only affects empty aircraft that are flying without any payload"
    ],
    "a": 2,
    "e": "Thin air and heavy weight compound, so a loaded aircraft climbs the worst.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Wind",
    "q": "On final approach in a gusty crosswind, the pilot should:",
    "c": [
      "Descend as fast as possible",
      "Slow down and be ready to abort the landing",
      "Ignore the gusts",
      "Add extra payload weight for more hover stability"
    ],
    "a": 1,
    "e": "Gusty crosswinds cut control margin, so approach slowly and be ready to go around.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Battery",
    "q": "A lithium battery that has puffed or swollen should be:",
    "c": [
      "Removed from service and not flown",
      "Stored at full charge",
      "Flown until empty",
      "Charged fully and reused"
    ],
    "a": 0,
    "e": "A swollen pack is damaged and unsafe, so retire it rather than fly it.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Maneuverability",
    "q": "Loading a drone near its maximum weight most affects:",
    "c": [
      "The visual line of sight rule for the operation",
      "Only the outward appearance of the aircraft",
      "Acceleration, stopping distance, and responsiveness",
      "The aircraft registration rule that applies to the drone"
    ],
    "a": 2,
    "e": "Added weight raises inertia, so the aircraft accelerates, stops, and responds more slowly.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "In a METAR, the group '09010KT' means wind from:",
    "c": [
      "090 at 100 knots",
      "10 degrees at 9 knots",
      "090 degrees at 10 knots",
      "9 degrees at 10 knots"
    ],
    "a": 2,
    "e": "The first three digits are wind direction in degrees and the next two are speed in knots.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "In a METAR, the group 'RMK' introduces:",
    "c": [
      "A required minimum",
      "A runway marking",
      "Remarks with additional detail",
      "The forecast section"
    ],
    "a": 2,
    "e": "RMK begins the remarks section, where extra observed detail is added.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "A METAR reporting 'FG' with '1/4SM' visibility indicates:",
    "c": [
      "A few scattered clouds overhead",
      "Fog severely reducing visibility",
      "Light and variable surface winds",
      "A gust front moving through the area"
    ],
    "a": 1,
    "e": "FG is fog, and at a quarter mile it is a serious hazard to flight.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "Fronts",
    "q": "The passage of a front is typically marked by:",
    "c": [
      "A wind shift with temperature and pressure changes",
      "A guaranteed clearing of all clouds within a few minutes",
      "Only a temperature rise, with no change in wind or pressure",
      "No noticeable change at all in the surface conditions"
    ],
    "a": 0,
    "e": "As a front passes, wind, temperature, and pressure all shift across the boundary.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Atmosphere",
    "q": "Air that resists vertical motion is described as:",
    "c": [
      "Stable",
      "Convective",
      "Unstable",
      "Saturated"
    ],
    "a": 0,
    "e": "Stable air resists rising motion, giving smooth conditions and layered clouds.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Fog",
    "q": "Upslope fog forms when:",
    "c": [
      "A fast-moving cold front passes through and drops the temperature",
      "Warm dry air sinks into a valley and compresses as it descends downward",
      "Moist air is pushed up rising terrain and cools to its dewpoint",
      "Surface winds die away at night over a calm body of open water"
    ],
    "a": 2,
    "e": "Upslope fog forms as moist air is forced up terrain and cools to saturation.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Winds Aloft",
    "q": "A winds aloft entry of '9900' means:",
    "c": [
      "99 knots from north",
      "Winds from 990 degrees",
      "Calm with 99 percent humidity",
      "Light and variable winds"
    ],
    "a": 3,
    "e": "The code 9900 means winds are light and variable, under about 5 knots.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "Hazards",
    "q": "With thunderstorms forecast in your flight window, the safest choice is to:",
    "c": [
      "Delay or cancel the flight",
      "Stay under 100 ft",
      "Fly quickly before they arrive",
      "Fly downwind of the cell"
    ],
    "a": 0,
    "e": "Thunderstorms bring violent turbulence, lightning, and shear, so delay or cancel.",
    "acs": "UA.III.B"
  },
  {
    "b": "Regulations",
    "s": "Currency",
    "q": "A remote pilot whose recurrent training has lapsed:",
    "c": [
      "Must retake the full proctored knowledge exam again",
      "May not act as remote PIC until it is completed",
      "May fly for 6 more months",
      "Loses the certificate forever"
    ],
    "a": 1,
    "e": "You must be current on recurrent training to act as remote PIC.",
    "acs": "UA.I.C"
  },
  {
    "b": "Regulations",
    "s": "Registration",
    "q": "Proof of registration during a Part 107 flight must be:",
    "c": [
      "Available to present on request",
      "Posted at the launch site",
      "Carried only at night",
      "Mailed to the FAA beforehand"
    ],
    "a": 0,
    "e": "The certificate of registration must be available to present on request during operations.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Eligibility",
    "q": "Beyond being at least 16 and English-proficient, an applicant must be:",
    "c": [
      "Physically and mentally able to operate safely",
      "The registered owner of the aircraft to be operated",
      "A licensed automobile driver in the state of residence",
      "A military veteran or active-duty service member"
    ],
    "a": 0,
    "e": "An applicant must be in a physical and mental condition to operate a small UAS safely.",
    "acs": "UA.I.C"
  },
  {
    "b": "Regulations",
    "s": "Alcohol & Drugs",
    "q": "Part 107 prohibits operating with a blood alcohol content of:",
    "c": [
      "0.08 percent or greater",
      "Any detectable amount",
      "0.04 percent or greater",
      "0.10 percent or greater"
    ],
    "a": 2,
    "e": "You may not operate at 0.04 percent or more, or within 8 hours of consuming alcohol.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Remote ID",
    "q": "Standard Remote ID broadcasts the aircraft's identity along with its:",
    "c": [
      "Flight plan",
      "Battery level",
      "Owner's home address",
      "Location and altitude"
    ],
    "a": 3,
    "e": "Standard Remote ID broadcasts identity, location, and altitude during flight.",
    "acs": "UA.I.F"
  },
  {
    "b": "Regulations",
    "s": "Supervision",
    "q": "A learner practicing on the controls under Part 107 must be:",
    "c": [
      "Within 100 feet of the supervising pilot and the control station at all times",
      "Already a certificate holder who has passed the initial knowledge test",
      "Directly supervised by a remote PIC able to take control immediately",
      "At least 18 years old and registered as a student with the FAA beforehand"
    ],
    "a": 2,
    "e": "A non-certificated person may fly only under a remote PIC able to take control at once.",
    "acs": "UA.I.B"
  },
  {
    "b": "Airspace",
    "s": "LAANC",
    "q": "LAANC authorizations are provided by:",
    "c": [
      "The drone manufacturer through the aircraft's companion application",
      "FAA-approved companies that process requests in near real time",
      "The local airport manager during published business hours only",
      "Mobile phone carriers that relay the request to the control tower"
    ],
    "a": 1,
    "e": "LAANC requests are handled by FAA-approved providers that return near-instant authorization.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "TFR",
    "q": "You learn a firefighting TFR now covers your planned site. You should:",
    "c": [
      "Fly below 400 ft through it",
      "Fly only at its edges",
      "Proceed, since drones are exempt",
      "Stay out unless specifically authorized"
    ],
    "a": 3,
    "e": "TFRs apply to drones, so do not enter without specific authorization.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Class G",
    "q": "To fly at 350 ft AGL in Class G airspace away from any airport, a pilot:",
    "c": [
      "Needs a waiver",
      "Must notify the nearest tower",
      "Needs LAANC authorization",
      "Needs no ATC authorization"
    ],
    "a": 3,
    "e": "Class G is uncontrolled, so no ATC authorization is needed, though all other rules apply.",
    "acs": "UA.II.A"
  },
  {
    "b": "Operations",
    "s": "VLOS",
    "q": "If terrain or smoke briefly blocks your view of the aircraft, you should:",
    "c": [
      "Hand off to a bystander",
      "Reposition to regain line of sight, or land",
      "Climb higher and continue",
      "Keep flying by the camera feed"
    ],
    "a": 1,
    "e": "Losing unaided sight breaks VLOS, so regain it or land.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Risk Management",
    "q": "External pressure, such as a waiting client, is dangerous because it can:",
    "c": [
      "Improve focus by giving the pilot a clear deadline to work toward",
      "Reduce fatigue because the pilot works faster under a deadline",
      "Lower the density altitude and make the air easier to fly in",
      "Push a pilot to fly in conditions they would otherwise avoid"
    ],
    "a": 3,
    "e": "External pressure can push a pilot past their personal minimums into an unsafe decision.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Preflight",
    "q": "If a firmware warning appears during preflight, the pilot should:",
    "c": [
      "Pull the battery, then continue the flight once it restarts cleanly",
      "Resolve it before flying rather than launch with a known issue",
      "Fly only under 100 feet until the warning eventually clears itself",
      "Ignore it and fly, since firmware warnings are usually harmless"
    ],
    "a": 1,
    "e": "Launching with a known unresolved issue is careless, so address it first.",
    "acs": "UA.V.F"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "In a METAR, the sky condition 'SKC' or 'CLR' means:",
    "c": [
      "No clouds observed",
      "Obscured sky",
      "Scattered clouds",
      "A broken ceiling"
    ],
    "a": 0,
    "e": "SKC and CLR both indicate no clouds were detected.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "A METAR wind group of '00000KT' indicates:",
    "c": [
      "Missing data",
      "A 100 knot wind",
      "Calm wind",
      "Wind from the north at 0 gusts"
    ],
    "a": 2,
    "e": "00000KT means the wind is calm.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "A METAR visibility group of '10SM' means visibility is:",
    "c": [
      "10 meters",
      "10 statute miles or more",
      "Exactly 10 nautical miles",
      "1.0 mile"
    ],
    "a": 1,
    "e": "10SM means visibility of 10 statute miles or greater, the maximum normally reported.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "In a METAR, the present weather '-RA' indicates:",
    "c": [
      "Recent rain",
      "No rain",
      "Heavy rain",
      "Light rain"
    ],
    "a": 3,
    "e": "A minus sign marks light intensity, so -RA is light rain.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "In a METAR, '+SHRA' indicates:",
    "c": [
      "Heavy rain showers",
      "Light showers",
      "Snow showers",
      "Scattered rain"
    ],
    "a": 0,
    "e": "A plus sign marks heavy intensity, so +SHRA is heavy rain showers.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "Sky Cover",
    "q": "A sky cover report of 'FEW' represents:",
    "c": [
      "1 to 2 eighths of cloud cover",
      "5 to 7 eighths",
      "No clouds",
      "Complete overcast"
    ],
    "a": 0,
    "e": "Few means 1 to 2 eighths of the sky is covered, too little to form a ceiling.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "Ceiling",
    "q": "A report shows 'SCT004 BKN008 OVC020'. The ceiling is:",
    "c": [
      "There is no ceiling because the layers are broken",
      "800 ft, the lowest broken or overcast layer",
      "2,000 ft, the height of the overcast layer above",
      "400 ft, the height of the lowest scattered layer"
    ],
    "a": 1,
    "e": "The ceiling is the lowest broken or overcast layer, so BKN008 sets it at 800 ft.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Stability",
    "q": "Puffy cumulus clouds building upward are a sign of:",
    "c": [
      "Calm high pressure",
      "Unstable air with possible turbulence",
      "Stable, smooth air",
      "A temperature inversion"
    ],
    "a": 1,
    "e": "Cumulus development signals unstable, rising air and the turbulence that comes with it.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Fronts",
    "q": "An occluded front forms when:",
    "c": [
      "A front stops moving",
      "A cold front overtakes a warm front",
      "Two warm fronts merge",
      "High pressure builds"
    ],
    "a": 1,
    "e": "An occluded front occurs as a faster cold front catches and lifts a warm front.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Fronts",
    "q": "A stationary front is likely to bring:",
    "c": [
      "A rapid and complete clearing of the sky within a few hours",
      "Strong downslope winds and rapidly warming air",
      "Prolonged clouds and precipitation as it lingers",
      "No noticeable change in the weather at the surface"
    ],
    "a": 2,
    "e": "A stationary front barely moves, so its clouds and precipitation can persist for a long time.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Hazards",
    "q": "Structural icing is a risk when there is:",
    "c": [
      "Visible moisture and temperatures near or below freezing",
      "High pressure with clear skies and warm surface temperatures",
      "A warm, humid afternoon with light and variable surface winds",
      "Dry air at any temperature, including well below freezing"
    ],
    "a": 0,
    "e": "Icing needs visible moisture plus temperatures at or below freezing.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "Wind direction in a METAR or TAF is referenced to:",
    "c": [
      "The nearest runway",
      "Grid north",
      "Magnetic north",
      "True north"
    ],
    "a": 3,
    "e": "METAR and TAF winds are true north, while tower and ATIS winds are magnetic.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "Fog",
    "q": "Radiation fog that formed overnight usually:",
    "c": [
      "Thickens through the afternoon",
      "Turns into a thunderstorm",
      "Burns off as the sun heats the ground",
      "Lasts for several days"
    ],
    "a": 2,
    "e": "Daytime heating warms the surface and dissipates radiation fog.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "TAF",
    "q": "A standard TAF is normally:",
    "c": [
      "Issued every single hour and valid for only 2 hours",
      "A one-time annual forecast",
      "Valid only for the surface",
      "Issued every 6 hours and valid for about 24 hours"
    ],
    "a": 3,
    "e": "TAFs are issued four times a day and typically cover a 24-hour period.",
    "acs": "UA.III.A"
  },
  {
    "b": "Charts",
    "s": "Airport Symbols",
    "q": "An anchor symbol on a sectional chart marks a:",
    "c": [
      "Heliport",
      "Military field",
      "Seaplane base",
      "Closed airport"
    ],
    "a": 2,
    "e": "An anchor denotes a seaplane base where water landings occur.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Airport Symbols",
    "q": "A circled letter H on a sectional chart marks a:",
    "c": [
      "Heliport",
      "Hospital only",
      "Hazard area",
      "High obstacle"
    ],
    "a": 0,
    "e": "A circled H marks a heliport.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Airport Symbols",
    "q": "A star above an airport symbol indicates the airport has:",
    "c": [
      "No runway lighting of any kind available for night operations",
      "A control tower that is in operation during published daytime hours",
      "A rotating beacon, typically operating sunset to sunrise",
      "Fuel services only, with no other facilities available on the field"
    ],
    "a": 2,
    "e": "A star marks a rotating beacon, which generally operates from sunset to sunrise.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Special Use",
    "q": "A parachute symbol on a sectional chart warns of:",
    "c": [
      "A balloon launch site",
      "A glider tow",
      "A parachute jumping area",
      "A noise-sensitive area"
    ],
    "a": 2,
    "e": "The parachute symbol marks an area of regular parachute jumping activity.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Special Use",
    "q": "A charted glider operations area tells a Part 107 pilot to:",
    "c": [
      "Expect only powered aircraft to be operating there",
      "Avoid the entire area, which is closed to all unmanned aircraft",
      "Treat the area as Class C airspace requiring authorization",
      "Watch for gliders, which can be quiet and hard to see"
    ],
    "a": 3,
    "e": "Glider areas warn of quiet, hard-to-see traffic, so stay especially vigilant.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Obstacles",
    "q": "Wind turbines on a sectional chart are shown:",
    "c": [
      "As small blue circles placed wherever the turbines are located",
      "As magenta flag symbols marking each individual turbine tower",
      "As obstacle symbols with their height, often in groups",
      "Only in the chart legend rather than on the chart itself"
    ],
    "a": 2,
    "e": "Wind turbines are charted as obstacles with heights, frequently grouped together.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Special Use",
    "q": "A blue boundary around a national park or wildlife refuge asks pilots to:",
    "c": [
      "Maintain a higher altitude and avoid disturbing the area",
      "Land inside the boundary and check in with a ranger",
      "Treat the entire area as prohibited airspace at all times",
      "Obtain a Temporary Flight Restriction from the FAA before entering"
    ],
    "a": 0,
    "e": "These advisory boundaries request higher flight to avoid disturbing wildlife and visitors.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Special Use",
    "q": "Restricted and prohibited areas on a sectional are outlined with:",
    "c": [
      "A row of dots",
      "A dashed green line",
      "A solid magenta line",
      "A blue hatched boundary"
    ],
    "a": 3,
    "e": "A blue hatched border outlines restricted and prohibited areas.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Symbols",
    "q": "Class C airspace shelf altitudes on a sectional are shown as:",
    "c": [
      "Blue shading whose darkness indicates the relative height of the airspace",
      "A dashed magenta line drawn around the outer edge of the airspace with no altitudes",
      "Single above-ground-level values printed in blue beside each runway end",
      "Magenta numbers giving the ceiling over the floor in hundreds of feet MSL"
    ],
    "a": 3,
    "e": "Class C segments list ceiling over floor in hundreds of feet MSL beside the magenta rings.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Navigation",
    "q": "Latitude and longitude lines on a sectional are used to:",
    "c": [
      "Show each of the different airspace classes",
      "Indicate wind direction",
      "Mark restricted areas",
      "Pinpoint a precise position on the chart"
    ],
    "a": 3,
    "e": "The latitude and longitude grid lets a pilot locate an exact position.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airport Symbols",
    "q": "A magenta airport symbol with small extensions usually shows:",
    "c": [
      "A non-towered airport drawn with its runway layout",
      "A towered airport, which would instead be charted in blue",
      "A heliport intended only for helicopter operations and landings",
      "A closed airfield that is no longer available for any landings"
    ],
    "a": 0,
    "e": "Magenta means no control tower, and the extensions depict the actual runways.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Airport Data",
    "q": "A small letter L in an airport data block usually indicates:",
    "c": [
      "The airport is large",
      "Low fuel only",
      "Runway lighting is available",
      "A left traffic pattern"
    ],
    "a": 2,
    "e": "An L in the data block indicates runway lighting is available, sometimes with limits.",
    "acs": "UA.II.B"
  },
  {
    "b": "Operations",
    "s": "ADM",
    "q": "The DECIDE model is a decision tool standing for:",
    "c": [
      "Detect, Engage, Climb, Inspect, Descend, Exit",
      "Decide, Execute, Confirm, Inspect, Deploy, End",
      "Define, Examine, Choose, Init, Drive, Exit",
      "Detect, Estimate, Choose, Identify, Do, Evaluate"
    ],
    "a": 3,
    "e": "DECIDE means Detect, Estimate, Choose, Identify, Do, and Evaluate.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Risk Management",
    "q": "The 3P risk model stands for:",
    "c": [
      "Pilot, Payload, Power",
      "Predict, Protect, Persist",
      "Plan, Prepare, Proceed",
      "Perceive, Process, Perform"
    ],
    "a": 3,
    "e": "The 3P model is Perceive the hazards, Process the risk, and Perform the response.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Risk Management",
    "q": "The level of a given risk is best understood as:",
    "c": [
      "Whether a similar event has ever happened to that pilot in the past",
      "A combination of how likely it is and how severe the outcome would be",
      "Only how likely the event is to happen, regardless of how bad it would be",
      "Only how severe the outcome would be, regardless of how likely it is"
    ],
    "a": 1,
    "e": "Risk combines the likelihood of an event with the severity of its outcome.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "See and Avoid",
    "q": "To meet see-and-avoid responsibilities, the remote PIC or observer should:",
    "c": [
      "Rely on the drone's onboard sensors alone to detect other aircraft",
      "Watch only the control screen, where all nearby traffic appears",
      "Continuously scan the sky around the aircraft for other traffic",
      "Look up once before launch and then focus on the control screen"
    ],
    "a": 2,
    "e": "Continuous scanning of the surrounding sky is how the crew spots and avoids other aircraft.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Site Survey",
    "q": "A preflight site survey should identify:",
    "c": [
      "Obstacles, people, and the airspace before the flight begins",
      "The aircraft's current resale value on the used equipment market",
      "Only the wind speed, since nothing else affects the flight",
      "The remote pilot's certificate number and date of issue"
    ],
    "a": 0,
    "e": "Surveying the site for obstacles, people, and airspace lets the pilot plan a safe operation.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Lost Link",
    "q": "A drone's return-to-home altitude should be set:",
    "c": [
      "Above the tallest obstacle along the return path",
      "Right at ground level so that the descent stays short",
      "Below 50 ft so the return stays quick",
      "At the maximum 400 ft for every flight"
    ],
    "a": 0,
    "e": "Setting return-to-home above the tallest obstacle prevents a collision during an automatic return.",
    "acs": "UA.V.C"
  },
  {
    "b": "Operations",
    "s": "Crew Roles",
    "q": "A visual observer in a Part 107 operation:",
    "c": [
      "Watches the aircraft and reports, but does not operate the controls",
      "Must hold a separate remote pilot certificate of their own",
      "Files the airspace authorization request with the FAA before launch",
      "Takes over flying the aircraft whenever the remote pilot is busy"
    ],
    "a": 0,
    "e": "The visual observer supports see-and-avoid but does not manipulate the controls.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Endurance",
    "q": "Planning a battery reserve before flight ensures the pilot can:",
    "c": [
      "Ignore the wind entirely because the reserve covers any added power use",
      "Land safely with margin instead of running the pack to empty",
      "Fly roughly twice as long as the battery would otherwise allow",
      "Skip the preflight inspection since the reserve handles surprises"
    ],
    "a": 1,
    "e": "A planned reserve leaves enough power to land safely rather than risking a dead pack aloft.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Right-of-Way",
    "q": "Yielding to a manned aircraft means the remote pilot must:",
    "c": [
      "Match the manned aircraft's altitude and follow it at a fixed distance",
      "Give way and stay well clear, not pass close ahead, above, or below",
      "Maintain the current heading and speed and let the other aircraft adjust",
      "Climb above the manned aircraft to pass safely over the top of it"
    ],
    "a": 1,
    "e": "Yielding means giving way and remaining well clear, never crossing close in front of or near the aircraft.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Hazardous Attitudes",
    "q": "The antidote to the anti-authority attitude is to remind yourself:",
    "c": [
      "It surely will not ever happen to me at all",
      "I can handle anything",
      "Follow the rules; they are usually right",
      "Do it quickly"
    ],
    "a": 2,
    "e": "The antidote to anti-authority is recognizing that the rules are usually there for good reason.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Time Pressure",
    "q": "Rushing a preflight to meet a deadline most directly increases the risk of:",
    "c": [
      "Sharper focus and quicker reactions once the aircraft is in the air",
      "Achieving longer battery life because the systems warm up more quickly",
      "Missing a problem that should have been caught on the ground",
      "Encountering smoother air because the flight begins earlier than planned"
    ],
    "a": 2,
    "e": "Hurrying the preflight lets ground-detectable problems slip through into the flight.",
    "acs": "UA.V.D"
  },
  {
    "b": "Airspace",
    "s": "Class B",
    "q": "In the core of Class B airspace, near the primary airport, the floor is usually:",
    "c": [
      "10,000 ft MSL",
      "700 ft AGL",
      "1,200 ft AGL",
      "At the surface"
    ],
    "a": 3,
    "e": "Class B reaches the surface in its core, with shelves stepping up farther out.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Planning",
    "q": "The best way to determine which airspace overlies your flight site is to:",
    "c": [
      "Ask a nearby bystander whether they have seen any aircraft overhead",
      "Wait until you are airborne and judge the airspace from the altitude",
      "Check a current sectional chart or an airspace app before flying",
      "Assume it is uncontrolled Class G unless a tower is clearly visible"
    ],
    "a": 2,
    "e": "Checking a current sectional or airspace tool before flight tells you exactly what airspace applies.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Class E Surface",
    "q": "A non-towered airport with an instrument approach may have Class E to the surface, charted as:",
    "c": [
      "A dashed magenta line, which requires authorization",
      "No marking at all, since Class E is never shown on charts",
      "A magenta flag symbol placed at the center of the airport",
      "A solid blue circle surrounding the entire airport area"
    ],
    "a": 0,
    "e": "A dashed magenta boundary marks Class E to the surface, which is controlled and needs authorization.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Special Use",
    "q": "The difference between a prohibited area and a restricted area is that a prohibited area:",
    "c": [
      "Is uncontrolled airspace that any pilot may enter at any time",
      "Applies only to unmanned aircraft and not to any manned traffic",
      "Permits flight below 400 feet above the ground without any prior coordination",
      "Bars all flight, while a restricted area may be entered with permission"
    ],
    "a": 3,
    "e": "Prohibited areas allow no flight at all, while restricted areas may be entered with permission.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "TFR",
    "q": "Temporary Flight Restrictions are commonly issued for:",
    "c": [
      "Clear-weather days when visibility and ceilings are well above minimums",
      "Routine drone operations that do not involve any manned aircraft traffic",
      "Hazards like wildfires, security like VIP movement, and special events",
      "Normal daily airport traffic during periods of heavy congestion"
    ],
    "a": 2,
    "e": "TFRs cover hazards, security needs, and special events, and they apply to drones.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "LAANC",
    "q": "Automatic LAANC authorization is:",
    "c": [
      "Available at any time through approved apps",
      "Issued by phone only",
      "Limited to weekends",
      "Only available during business hours"
    ],
    "a": 0,
    "e": "LAANC processes requests automatically around the clock through approved providers.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "Grid Altitude",
    "q": "If a UAS Facility Map grid shows 200 ft over your site, you may:",
    "c": [
      "Fly only up to 200 ft there under automatic authorization",
      "Still fly up to 400 ft as long as you stay within visual line of sight",
      "Ignore the grid because facility maps are only advisory for hobby flyers",
      "Fly only at night, when the published grid altitudes no longer apply"
    ],
    "a": 0,
    "e": "The grid ceiling can be below 400 ft, and you must honor that lower authorized altitude.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "Authorization",
    "q": "Receiving an airspace authorization to enter Class D:",
    "c": [
      "Removes the visual line of sight rule",
      "Does not exempt you from the other Part 107 rules",
      "Lets you exceed 400 ft AGL",
      "Allows flight over people"
    ],
    "a": 1,
    "e": "Authorization only grants airspace access; every other Part 107 limit still applies.",
    "acs": "UA.II.B"
  },
  {
    "b": "Regulations",
    "s": "Waivers",
    "q": "A request for a Part 107 waiver is submitted through:",
    "c": [
      "The FAA DroneZone portal",
      "A local flight school",
      "The aircraft manufacturer",
      "The control tower"
    ],
    "a": 0,
    "e": "Waiver requests are filed through the FAA DroneZone portal.",
    "acs": "UA.I.D"
  },
  {
    "b": "Regulations",
    "s": "Responsibility",
    "q": "Ultimate responsibility for the safety of a Part 107 operation rests with:",
    "c": [
      "The aircraft manufacturer",
      "The client",
      "The remote pilot in command",
      "Air traffic control"
    ],
    "a": 2,
    "e": "The remote PIC is directly responsible for and the final authority over the operation.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Currency",
    "q": "The updated Part 107 recurrent training now includes content on:",
    "c": [
      "Seaplane ratings",
      "Manned aircraft systems",
      "International flight",
      "Night operations"
    ],
    "a": 3,
    "e": "Recurrent training was updated to cover night operations along with the core knowledge areas.",
    "acs": "UA.I.C"
  },
  {
    "b": "Regulations",
    "s": "Registration",
    "q": "Registering a small unmanned aircraft for Part 107 is completed through:",
    "c": [
      "A state motor vehicle office",
      "The manufacturer's website",
      "A local airport",
      "The FAA DroneZone system"
    ],
    "a": 3,
    "e": "Aircraft registration is completed through the FAA DroneZone system.",
    "acs": "UA.I.B"
  },
  {
    "b": "Loading",
    "s": "Center of Gravity",
    "q": "Keeping the center of gravity within the manufacturer's limits gives:",
    "c": [
      "Predictable, stable handling",
      "A higher weight limit",
      "Longer battery life",
      "Faster acceleration only"
    ],
    "a": 0,
    "e": "A center of gravity within limits keeps the aircraft stable and predictable to control.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Battery",
    "q": "As battery voltage drops late in a flight, the aircraft may:",
    "c": [
      "Gain power as the remaining cells discharge and deliver a brief surge of current",
      "Climb faster and more efficiently as the lighter battery reduces the total weight",
      "Trigger an automatic return or landing, so a reserve should be planned",
      "Extend its total range because the flight controller switches to a power-saving mode"
    ],
    "a": 2,
    "e": "Low voltage can force an automatic return or landing, which is why a reserve is planned.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Performance",
    "q": "Hovering a multirotor is power-intensive, so a long hover will:",
    "c": [
      "Cool the motors because the aircraft is not moving through the air",
      "Slowly recharge the battery using the spinning rotor blades",
      "Have no effect on endurance since hovering uses very little power",
      "Use significant battery and shorten the remaining flight time"
    ],
    "a": 3,
    "e": "Hovering demands constant high power, draining the battery and cutting remaining flight time.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Maneuverability",
    "q": "A heavier aircraft carries more energy, so on descent and landing the pilot should:",
    "c": [
      "Descend as fast as possible",
      "Allow more room and a gentler approach",
      "Add more payload",
      "Cut power abruptly"
    ],
    "a": 1,
    "e": "Greater mass means more energy to manage, so heavier aircraft need a gentler, roomier approach.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Operations",
    "s": "Hazardous Attitudes",
    "q": "The antidote to the macho attitude is to tell yourself:",
    "c": [
      "Taking chances is foolish",
      "Follow the rules",
      "It cannot happen to me",
      "Do it quickly"
    ],
    "a": 0,
    "e": "The antidote to macho is recognizing that taking unnecessary chances is foolish.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Hazardous Attitudes",
    "q": "The antidote to impulsivity is to tell yourself:",
    "c": [
      "It will not happen to me",
      "Not so fast; think first",
      "Rules are for others",
      "I am helpless"
    ],
    "a": 1,
    "e": "The antidote to impulsivity is to slow down and think before acting.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Hazardous Attitudes",
    "q": "The antidote to invulnerability is to tell yourself:",
    "c": [
      "It could happen to me",
      "Do it now",
      "Taking chances is foolish",
      "I cannot make a difference"
    ],
    "a": 0,
    "e": "The antidote to invulnerability is accepting that an accident could happen to you.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Hazardous Attitudes",
    "q": "The antidote to resignation is to tell yourself:",
    "c": [
      "The rules are really meant for others",
      "It cannot ever happen to me out here",
      "Just hurry up now before the chance slips away",
      "I am not helpless; I can make a difference"
    ],
    "a": 3,
    "e": "The antidote to resignation is recognizing you can influence the outcome.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Over Vehicles",
    "q": "Flying a drone directly over a moving vehicle is:",
    "c": [
      "Restricted, like flight over people, unless conditions or a category are met",
      "Always allowed below 400 feet as long as the vehicle is on a public road",
      "Allowed whenever the vehicle is stopped at a traffic light or stop sign",
      "Never restricted, because the occupants are fully shielded by the vehicle body"
    ],
    "a": 0,
    "e": "Flight over moving vehicles is restricted much like flight over people unless the operation meets the rules.",
    "acs": "UA.I.E"
  },
  {
    "b": "Operations",
    "s": "Preflight",
    "q": "Before takeoff, a pilot should confirm:",
    "c": [
      "The aircraft's exterior color and paint condition",
      "The client's schedule for the rest of the day",
      "Only that the propellers spin freely when the motors arm",
      "A solid GPS lock and that the home point is set"
    ],
    "a": 3,
    "e": "Confirming GPS lock and a set home point ensures features like return-to-home will work.",
    "acs": "UA.V.F"
  },
  {
    "b": "Operations",
    "s": "Loss of GPS",
    "q": "If GPS is lost in flight, the pilot should be prepared to:",
    "c": [
      "Let it drift until GPS returns",
      "Hand off to a bystander",
      "Fly the aircraft manually and land safely",
      "Increase altitude and wait"
    ],
    "a": 2,
    "e": "A pilot should be ready to take manual control and land if the aircraft loses GPS.",
    "acs": "UA.V.C"
  },
  {
    "b": "Operations",
    "s": "Weather Briefing",
    "q": "Obtaining a weather briefing before flight helps a pilot:",
    "c": [
      "Anticipate hazards like wind, ceilings, and storms",
      "Choose the most appropriate paint color for the drone",
      "Skip the on-site preflight survey entirely",
      "Avoid having to register the aircraft"
    ],
    "a": 0,
    "e": "A weather briefing reveals wind, ceilings, visibility, and storms that affect the go decision.",
    "acs": "UA.III.A"
  },
  {
    "b": "Operations",
    "s": "Go No-Go",
    "q": "If conditions deteriorate below a pilot's personal minimums in flight, the right action is to:",
    "c": [
      "Climb to 400 ft",
      "Continue and finish quickly",
      "Ignore the change",
      "End the flight and land"
    ],
    "a": 3,
    "e": "When conditions fall below personal minimums, the safe choice is to land and end the flight.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Emergency Response",
    "q": "Flying a drone near a wildfire or active emergency scene:",
    "c": [
      "Is fine as long as the aircraft stays above 400 feet over the scene",
      "Is encouraged so the footage can be shared with the emergency responders",
      "Is dangerous and prohibited, as it can ground firefighting aircraft",
      "Requires only a brief verbal notice to the on-scene incident commander"
    ],
    "a": 2,
    "e": "Drones near wildfires or emergencies endanger and can ground crewed response aircraft, so do not fly there.",
    "acs": "UA.V.C"
  },
  {
    "b": "Operations",
    "s": "Failsafe",
    "q": "Before flying, a pilot should know the aircraft's failsafe behavior so they can:",
    "c": [
      "Predict what it does on a lost link or low battery",
      "Operate the aircraft without performing a preflight check",
      "Safely exceed the published maximum takeoff weight limit",
      "Skip the preflight briefing to save time before launch"
    ],
    "a": 0,
    "e": "Knowing the failsafe response to a lost link or low battery lets the pilot plan for it.",
    "acs": "UA.V.C"
  },
  {
    "b": "Operations",
    "s": "Transfer of Control",
    "q": "During a coordinated transfer of control between two remote pilots:",
    "c": [
      "Neither pilot is responsible during the handoff itself",
      "Only one is the responsible remote PIC at any moment",
      "Both pilots are the responsible remote PIC at the same time",
      "A nearby bystander temporarily becomes the remote PIC"
    ],
    "a": 1,
    "e": "Control may pass between qualified pilots, but only one is the responsible remote PIC at a time.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Distance Judgment",
    "q": "Because judging an aircraft's altitude and distance is harder far away, a pilot should:",
    "c": [
      "Keep the aircraft close enough to see its position and orientation clearly",
      "Ignore orientation and focus solely on keeping the battery level above reserve",
      "Rely only on the map view in the controller app to judge the aircraft's location",
      "Fly the aircraft out as far as the control link signal will reliably reach"
    ],
    "a": 0,
    "e": "Position and attitude are hard to judge at range, so keep the aircraft close enough to see clearly.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Bystander Safety",
    "q": "A safe operation keeps uninvolved people:",
    "c": [
      "Clear of the launch and landing zone and out from under the aircraft",
      "Inside the control station alongside the remote pilot for the whole flight",
      "Holding the aircraft steady during launch and recovery each time",
      "Directly below the aircraft so they get the best possible view"
    ],
    "a": 0,
    "e": "Keeping bystanders clear of the launch zone and out from under the aircraft protects them from injury.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Communication",
    "q": "For a multi-person operation, the crew should agree on:",
    "c": [
      "Who gets to keep the footage afterward",
      "A clear method to communicate during the flight",
      "The color scheme and overall styling of the aircraft",
      "Nothing needs to be agreed in advance"
    ],
    "a": 1,
    "e": "Agreeing on a communication method keeps the remote PIC and observer coordinated in flight.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "ADM",
    "q": "When a pilot is unsure whether a flight is safe or legal, the best choice is to:",
    "c": [
      "Not fly until the doubt is resolved",
      "Fly only briefly",
      "Fly and find out",
      "Ask a bystander to decide"
    ],
    "a": 0,
    "e": "When in doubt, do not fly until the safety or legality question is resolved.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Obstacle Awareness",
    "q": "Before maneuvering at low altitude, a pilot should scan for:",
    "c": [
      "The amount of cloud cover overhead only",
      "The remote pilot certificate expiration date",
      "Only the battery level shown on the controller",
      "Wires, poles, and towers that are hard to see"
    ],
    "a": 3,
    "e": "Thin wires and towers are easy to miss, so scan for them before any low maneuvering.",
    "acs": "UA.II.B"
  },
  {
    "b": "Operations",
    "s": "Recordkeeping",
    "q": "Keeping a flight log under Part 107 is:",
    "c": [
      "Required only at night",
      "Good practice, though not required by the rule",
      "Prohibited",
      "Strictly required by the rule before every flight"
    ],
    "a": 1,
    "e": "Part 107 does not require a logbook, but accurate records are a useful safety habit.",
    "acs": "UA.I.A"
  },
  {
    "b": "Operations",
    "s": "Daylight Awareness",
    "q": "Knowing the local sunset time matters because it determines when:",
    "c": [
      "The certificate expires",
      "Anti-collision lighting and night rules apply",
      "The battery must be charged",
      "The aircraft must be registered"
    ],
    "a": 1,
    "e": "Sunset marks when civil twilight and night lighting requirements begin to apply.",
    "acs": "UA.I.B"
  },
  {
    "b": "Airspace",
    "s": "Class C",
    "q": "The top of Class C airspace is typically:",
    "c": [
      "10,000 ft MSL across the entire charted area",
      "About 4,000 ft above the airport elevation",
      "700 ft AGL, matching the floor of Class E nearby",
      "18,000 ft MSL, the altitude where Class A airspace begins"
    ],
    "a": 1,
    "e": "Class C generally tops out around 4,000 ft above the airport elevation.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Class D",
    "q": "When the control tower at a Class D airport closes for the night, the airspace usually:",
    "c": [
      "Stays Class D",
      "Becomes Class B",
      "Becomes prohibited",
      "Reverts to Class E or Class G"
    ],
    "a": 3,
    "e": "Class D depends on an operating tower, so it reverts to Class E or G when the tower closes.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Class E",
    "q": "Far from airports, en route Class E airspace often begins at:",
    "c": [
      "700 ft AGL",
      "18,000 ft MSL",
      "14,500 ft MSL",
      "The surface"
    ],
    "a": 2,
    "e": "Where not otherwise designated, en route Class E begins at 14,500 ft MSL.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Authorization",
    "q": "Which airspace does NOT require Part 107 authorization for a drone?",
    "c": [
      "Surface Class E established to support an instrument approach",
      "Class C airspace surrounding a busier airport that provides radar service",
      "Class D airspace surrounding an airport with an operating control tower",
      "Class E that begins at 700 or 1,200 ft AGL, not at the surface"
    ],
    "a": 3,
    "e": "Part 107 needs authorization only for B, C, D, and surface Class E, not for Class E that starts above the ground.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "Class G Ceiling",
    "q": "The top of Class G airspace is found where:",
    "c": [
      "The charted floor of the traffic pattern ends, usually near 400 feet AGL",
      "The overlying controlled airspace begins, often 700 or 1,200 ft AGL",
      "It always reaches exactly 18,000 feet regardless of the surrounding airspace",
      "Class A airspace begins, at 18,000 feet mean sea level across the country"
    ],
    "a": 1,
    "e": "Class G extends up to the base of the overlying controlled airspace, commonly 700 or 1,200 ft AGL.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "LAANC vs DroneZone",
    "q": "LAANC and FAA DroneZone differ in that LAANC:",
    "c": [
      "Provides authorization only for manned aircraft operating in controlled airspace near airports",
      "Is available only for night operations that require anti-collision lighting and extra training",
      "Gives near-instant authorization, while DroneZone handles manual or further-out requests",
      "Replaces the aircraft registration requirement for drones flown under Part 107 rules"
    ],
    "a": 2,
    "e": "LAANC returns near-instant authorization up to grid limits, while DroneZone handles manual and special requests.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "Restricted Area",
    "q": "To operate inside an active Restricted Area, a pilot must:",
    "c": [
      "Obtain permission from the controlling agency",
      "Simply stay under 400 ft above the ground",
      "Do nothing at all if the transit is brief",
      "File a Temporary Flight Restriction beforehand"
    ],
    "a": 0,
    "e": "An active restricted area may be entered only with permission from its controlling agency.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "MOA",
    "q": "The status of a Military Operations Area can be checked through:",
    "c": [
      "The aircraft's flight manual, which lists every active military area",
      "NOTAMs and the controlling agency, with hours often shown on the chart",
      "Only radio contact with the nearest airport traffic control tower",
      "The aircraft registration database maintained on the FAA DroneZone website"
    ],
    "a": 1,
    "e": "MOA activity is published via NOTAMs and the controlling agency, with times often listed on the chart.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Low Altitude",
    "q": "Operating at only 100 ft AGL inside Class D airspace:",
    "c": [
      "Is automatically allowed",
      "Needs no authorization because it is low",
      "Still requires authorization",
      "Requires a waiver"
    ],
    "a": 2,
    "e": "Controlled airspace requires authorization at any altitude, even very low operations.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "National Parks",
    "q": "Launching or landing a drone within a US National Park is generally:",
    "c": [
      "Treated exactly the same as Class G airspace",
      "Allowed provided you remain below 400 ft above ground",
      "Prohibited by National Park Service rules",
      "Allowed once a LAANC authorization is obtained"
    ],
    "a": 2,
    "e": "The National Park Service prohibits launching and landing drones within park boundaries.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Communication",
    "q": "To operate in authorized controlled airspace, a Part 107 pilot:",
    "c": [
      "Does not need two-way radio contact with ATC; authorization is handled digitally",
      "Must maintain a continuous listening watch on the emergency frequency 121.5 throughout",
      "Must file an instrument flight rules plan before entering the airspace",
      "Must talk to the control tower continuously throughout the entire operation"
    ],
    "a": 0,
    "e": "Small UAS do not maintain radio contact with ATC; the digital authorization is what grants access.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "Chart Currency",
    "q": "When checking airspace, a pilot should always use:",
    "c": [
      "A standard highway road map of the area",
      "The current edition of the sectional chart",
      "Whatever old chart happens to be on hand",
      "A surface analysis weather chart for the day"
    ],
    "a": 1,
    "e": "Airspace changes over time, so always reference the current edition of the sectional.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "TFR",
    "q": "A disaster-relief TFR over a flooded area:",
    "c": [
      "Ends automatically at 400 feet above the ground for small drones",
      "Applies only to helicopters and other manned rescue aircraft",
      "Can be safely ignored by drones that stay within visual line of sight",
      "Restricts drone flight there without specific authorization"
    ],
    "a": 3,
    "e": "Disaster-relief TFRs apply to drones, so do not enter without specific authorization.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Class B",
    "q": "Authorization to fly a drone in Class B airspace is usually obtained:",
    "c": [
      "Only with a specific waiver granted in advance by the FAA",
      "By calling the primary airport's control tower before takeoff",
      "Automatically, as long as the flight stays below 400 feet AGL",
      "Through LAANC where available, or DroneZone otherwise"
    ],
    "a": 3,
    "e": "Class B access comes through LAANC where it is supported, or through DroneZone otherwise.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Stadium TFR",
    "q": "The standing stadium TFR is in effect:",
    "c": [
      "Only during playoff games and major championship events",
      "All day every day, whether or not an event is happening",
      "Only during the event window defined by the NOTAM",
      "Only at night, regardless of when events are scheduled"
    ],
    "a": 2,
    "e": "The stadium TFR applies during the event window, from one hour before to one hour after.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Position Awareness",
    "q": "Knowing exactly where the aircraft is relative to airspace boundaries is:",
    "c": [
      "Only needed at night",
      "Handled automatically by ATC",
      "Not necessary in Class G",
      "The remote pilot's responsibility"
    ],
    "a": 3,
    "e": "The remote pilot is responsible for knowing the aircraft's position relative to airspace boundaries.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "Special Use",
    "q": "A pilot planning near a charted restricted area should first:",
    "c": [
      "Check whether it is active and get permission if needed",
      "Treat it as uncontrolled Class G and fly without authorization",
      "Assume it is always inactive outside of normal business hours",
      "Fly through it quickly to spend as little time inside as possible"
    ],
    "a": 0,
    "e": "Restricted areas may be active, so check status and obtain permission before operating inside.",
    "acs": "UA.II.A"
  },
  {
    "b": "Regulations",
    "s": "Commercial Use",
    "q": "Flying a drone to take photos you will sell must be done under:",
    "c": [
      "A manned pilot certificate",
      "No rules",
      "Part 107",
      "The recreational exception"
    ],
    "a": 2,
    "e": "Any flight for a business or compensation falls under Part 107, not the recreational exception.",
    "acs": "UA.I.A"
  },
  {
    "b": "Regulations",
    "s": "Knowledge Test",
    "q": "The passing score on the Part 107 knowledge test is:",
    "c": [
      "100 percent",
      "80 percent",
      "60 percent",
      "70 percent"
    ],
    "a": 3,
    "e": "A score of 70 percent or higher is required to pass the Part 107 knowledge test.",
    "acs": "UA.I.C"
  },
  {
    "b": "Regulations",
    "s": "Knowledge Test",
    "q": "If you fail the Part 107 knowledge test, you must wait before retaking it:",
    "c": [
      "30 days",
      "24 hours",
      "6 months",
      "14 calendar days"
    ],
    "a": 3,
    "e": "After a failed knowledge test, you must wait 14 calendar days before retesting.",
    "acs": "UA.I.C"
  },
  {
    "b": "Regulations",
    "s": "Inspection",
    "q": "The remote pilot certificate must be presented for inspection on request by:",
    "c": [
      "Only the FAA",
      "The original aircraft seller or its dealer",
      "Any bystander",
      "The FAA, NTSB, TSA, or law enforcement"
    ],
    "a": 3,
    "e": "The certificate must be shown on request to the FAA, NTSB, TSA, or law enforcement.",
    "acs": "UA.I.A"
  },
  {
    "b": "Regulations",
    "s": "Applicability",
    "q": "Part 107 applies to:",
    "c": [
      "All aircraft over 55 lb, including manned general aviation planes",
      "Public aircraft operated only by government agencies and police",
      "Manned aircraft only, flown by certificated private pilots",
      "Civil small unmanned aircraft weighing less than 55 lb"
    ],
    "a": 3,
    "e": "Part 107 governs civil small unmanned aircraft that weigh less than 55 lb.",
    "acs": "UA.I.A"
  },
  {
    "b": "Regulations",
    "s": "Public Operations",
    "q": "A government agency flying a drone may instead operate under:",
    "c": [
      "A Certificate of Waiver or Authorization (COA)",
      "A standard state driver's license held by the pilot",
      "No rules at all, since government flights are exempt",
      "A manned-aircraft type rating held by the operator"
    ],
    "a": 0,
    "e": "Public aircraft operations can be conducted under a COA rather than Part 107.",
    "acs": "UA.I.A"
  },
  {
    "b": "Regulations",
    "s": "Registration Marking",
    "q": "The registration number marked on a drone must be:",
    "c": [
      "Hidden inside the body",
      "Broadcast by radio",
      "Painted only in red",
      "Legible and readable without tools"
    ],
    "a": 3,
    "e": "The registration marking must be legible and readable without disassembling the aircraft.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Drug and Alcohol",
    "q": "Refusing a drug or alcohol test, or a related conviction, can lead to:",
    "c": [
      "A longer permitted flight time as a one-time administrative penalty",
      "Denial, suspension, or revocation of the certificate",
      "No consequences, since these tests do not apply to remote pilots",
      "A written warning only, with no effect on the remote certificate"
    ],
    "a": 1,
    "e": "Refusing testing or a drug or alcohol conviction can result in denial, suspension, or revocation.",
    "acs": "UA.I.C"
  },
  {
    "b": "Regulations",
    "s": "Recreational Exception",
    "q": "The limited recreational exception may not be used to:",
    "c": [
      "Fly in uncontrolled Class G airspace below 400 feet",
      "Conduct commercial or compensated flights",
      "Fly during daylight hours in good clear weather",
      "Fly under 400 feet above the ground at any time"
    ],
    "a": 1,
    "e": "The recreational exception is for hobby flying only and cannot cover commercial operations.",
    "acs": "UA.I.A"
  },
  {
    "b": "Regulations",
    "s": "Pilot in Command",
    "q": "To act as the remote pilot in command, a person must:",
    "c": [
      "Be over 21",
      "Own the aircraft",
      "Hold a remote pilot certificate",
      "Have a manned rating"
    ],
    "a": 2,
    "e": "Only a holder of a remote pilot certificate may act as the remote PIC.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "TRUST",
    "q": "The TRUST certificate:",
    "c": [
      "Allows unrestricted flight directly over people",
      "Does not authorize commercial operations",
      "Replaces Part 107",
      "Expires every year"
    ],
    "a": 1,
    "e": "TRUST covers recreational flying only and does not authorize commercial work.",
    "acs": "UA.I.A"
  },
  {
    "b": "Regulations",
    "s": "Airspace Compliance",
    "q": "For each flight, the remote PIC must ensure:",
    "c": [
      "A bystander is present to watch the aircraft take off",
      "The flight is recorded on video from start to finish",
      "Any required airspace authorization is obtained beforehand",
      "The aircraft is the newest model currently available from the manufacturer"
    ],
    "a": 2,
    "e": "The remote PIC is responsible for obtaining any required airspace authorization before flying.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Currency",
    "q": "Completing recurrent training every 24 calendar months lets a pilot:",
    "c": [
      "Legally fly aircraft that weigh over 55 lb",
      "Avoid having to register the aircraft at all",
      "Continue exercising remote pilot privileges",
      "Skip the airspace authorization rules entirely"
    ],
    "a": 2,
    "e": "Staying current with recurrent training keeps a pilot eligible to exercise remote pilot privileges.",
    "acs": "UA.I.C"
  },
  {
    "b": "Regulations",
    "s": "Registration",
    "q": "Before a registered drone's first flight under Part 107, the owner must:",
    "c": [
      "File a flight plan",
      "Mark it with the registration number",
      "Repaint it",
      "Notify the local airport"
    ],
    "a": 1,
    "e": "The aircraft must display its registration number before it is flown.",
    "acs": "UA.I.B"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "In a METAR, a temperature group of 'M06' means:",
    "c": [
      "6 degrees above standard",
      "6 statute miles",
      "Minus 6 degrees Celsius",
      "Mach 0.6"
    ],
    "a": 2,
    "e": "An M prefix means a negative value, so M06 is minus 6 degrees Celsius.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "Winds Aloft",
    "q": "A winds aloft entry of '2718' means wind from:",
    "c": [
      "270 degrees at 18 knots",
      "271 degrees at 8 knots",
      "2,700 ft at 18 knots",
      "27 degrees at 18 knots"
    ],
    "a": 0,
    "e": "The first two digits are tens of degrees and the next two are speed, so 2718 is 270 at 18 knots.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "TAF",
    "q": "A visibility group of 'P6SM' in a forecast means visibility:",
    "c": [
      "Plus or minus 6 miles",
      "Exactly 6 nautical miles",
      "6 meters",
      "Greater than 6 statute miles"
    ],
    "a": 3,
    "e": "P6SM means visibility is forecast to be greater than 6 statute miles.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "In a METAR, the present weather code 'HZ' indicates:",
    "c": [
      "Hail",
      "Hazardous icing",
      "High winds",
      "Haze"
    ],
    "a": 3,
    "e": "HZ is the code for haze, which reduces visibility.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "In a METAR, the code 'DZ' indicates:",
    "c": [
      "Daytime",
      "Dust",
      "Drizzle",
      "A drop zone"
    ],
    "a": 2,
    "e": "DZ is the code for drizzle.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "Hazards",
    "q": "Towering cumulus or a cumulonimbus cloud signals:",
    "c": [
      "Light and variable winds near the surface",
      "Steadily improving visibility in the area",
      "A developing or active thunderstorm to avoid",
      "Calm and stable air that is smooth to fly in"
    ],
    "a": 2,
    "e": "Towering cumulus and cumulonimbus mark convective storms with severe turbulence to avoid.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Hazards",
    "q": "Standing lenticular clouds near mountains warn of:",
    "c": [
      "Calm, smooth air on the downwind side of the range",
      "An approaching warm front with steady rain",
      "Mountain wave activity and turbulence",
      "Fog forming in the valleys below the peaks"
    ],
    "a": 2,
    "e": "Smooth lens-shaped lenticular clouds mark mountain wave activity and the turbulence around it.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Altitude",
    "q": "Pressure altitude is the altitude read when the altimeter is set to:",
    "c": [
      "30.00 inches",
      "The field elevation",
      "The local setting",
      "29.92 inches of mercury"
    ],
    "a": 3,
    "e": "Pressure altitude is height above the standard datum, found by setting the altimeter to 29.92.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Density Altitude",
    "q": "On a standard day, density altitude equals:",
    "c": [
      "Zero",
      "Indicated altitude plus 1,000 ft",
      "True altitude minus 1,000 ft",
      "Pressure altitude"
    ],
    "a": 3,
    "e": "Under standard temperature, density altitude and pressure altitude are the same.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Local Winds",
    "q": "A land breeze at night along a coast flows:",
    "c": [
      "Straight up from the surface toward the cloud layer above",
      "From the cooling land out toward the warmer water",
      "From the water inland toward the land",
      "Only during active coastal storms at night"
    ],
    "a": 1,
    "e": "At night the land cools faster than the water, so the breeze flows offshore.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Hazards",
    "q": "Frost is most likely to form when the night is:",
    "c": [
      "Warm and humid with a light breeze moving across the surface",
      "Clear and calm with the surface at or below freezing",
      "Cloudy and windy, which keeps the surface temperature from dropping",
      "Stormy, with heavy rain and gusty winds throughout the night"
    ],
    "a": 1,
    "e": "Clear, calm nights let the surface cool to freezing, allowing frost to form.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Wind Shear",
    "q": "Wind shear is commonly encountered near:",
    "c": [
      "Only above 10,000 ft",
      "Only over open water",
      "Fronts and temperature inversions",
      "Calm high pressure"
    ],
    "a": 2,
    "e": "Sharp changes in wind near fronts and inversions create low-level wind shear.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Fog",
    "q": "A large temperature and dewpoint spread generally means:",
    "c": [
      "Guaranteed thunderstorms",
      "Freezing rain",
      "Higher cloud bases and lower fog risk",
      "Imminent fog"
    ],
    "a": 2,
    "e": "A wide temperature-dewpoint spread means drier air, higher cloud bases, and less fog risk.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Wind",
    "q": "Gusty surface winds are especially challenging for a small UAS because:",
    "c": [
      "Gusts only ever affect the larger manned aircraft nearby",
      "It is immune to wind",
      "Its light weight makes it easier to push off course",
      "Wind improves its battery"
    ],
    "a": 2,
    "e": "A light small UAS is more easily displaced by gusts than a heavier aircraft, demanding constant correction.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Fronts",
    "q": "Compared with a warm front, a cold front typically:",
    "c": [
      "Brings no change in wind direction as it passes over the area",
      "Moves faster and produces a sharper, briefer band of weather",
      "Forms only at night and dissipates shortly after sunrise each day",
      "Moves more slowly and brings steady, widespread, light rain"
    ],
    "a": 1,
    "e": "Cold fronts move faster and lift air more steeply, giving a narrow, intense band of weather.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "A METAR is best described as a report that is:",
    "c": [
      "Issued once per year for each reporting airport",
      "Valid only above 1,000 feet over the reporting station",
      "Observed at a point in time, usually updated hourly",
      "A multi-day forecast of the conditions expected ahead"
    ],
    "a": 2,
    "e": "A METAR is an observation of current conditions, normally updated about every hour.",
    "acs": "UA.III.A"
  },
  {
    "b": "Charts",
    "s": "Navigation",
    "q": "A non-directional beacon (NDB) on a sectional is shown as:",
    "c": [
      "A magenta flag",
      "A blue hexagon",
      "A solid blue square",
      "A magenta circle of dots"
    ],
    "a": 3,
    "e": "An NDB is drawn as a circle made of small magenta dots.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Scale",
    "q": "A VFR sectional chart uses a scale of:",
    "c": [
      "1:1,000,000",
      "1:100,000",
      "1:24,000",
      "1:500,000"
    ],
    "a": 3,
    "e": "Sectional charts are drawn at a scale of 1 to 500,000.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Chart Types",
    "q": "For the detail around a busy Class B airport, the better chart is the:",
    "c": [
      "IFR low-altitude en route chart for the area",
      "World aeronautical chart at a small scale",
      "Surface analysis chart issued each morning",
      "Terminal Area Chart, drawn at a larger scale"
    ],
    "a": 3,
    "e": "A Terminal Area Chart shows Class B areas at a larger scale than the sectional for more detail.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airport Data",
    "q": "To find an airport's control tower frequency on a sectional, look for:",
    "c": [
      "The compass rose drawn around the nearest navigation aid on the chart",
      "The Maximum Elevation Figure printed in each quadrangle of the chart",
      "CT followed by the frequency in the airport data",
      "The terrain tint, which is darkest over the highest ground nearby"
    ],
    "a": 2,
    "e": "The airport data block lists the tower frequency after the letters CT.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Landmarks",
    "q": "Roads, railroads, and rivers on a sectional are useful as:",
    "c": [
      "Boundaries that mark where airspace classes change",
      "Visual landmarks for navigation and position",
      "Reliable indicators of the surface wind direction",
      "Indicators of the height of nearby charted obstacles"
    ],
    "a": 1,
    "e": "Linear features like roads and rivers serve as visual checkpoints for navigation.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Landmarks",
    "q": "Cities and large towns on a sectional are typically shown in:",
    "c": [
      "Yellow",
      "Green",
      "Magenta",
      "Blue"
    ],
    "a": 0,
    "e": "Populated areas are shaded yellow so they stand out as landmarks.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Legend",
    "q": "The meaning of an unfamiliar symbol on a sectional is found in:",
    "c": [
      "The margin tabulation only",
      "The chart legend",
      "The compass rose",
      "The airport data block"
    ],
    "a": 1,
    "e": "The chart legend defines every symbol used on the sectional.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Boundaries",
    "q": "A dashed line separating two parts of a sectional with a one-hour time difference marks a:",
    "c": [
      "Time zone boundary",
      "Magnetic variation line",
      "Restricted area",
      "State line only"
    ],
    "a": 0,
    "e": "A time zone boundary is charted where local time changes by an hour.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Symbols",
    "q": "A soft magenta vignette differs from a dashed magenta line in that the vignette marks:",
    "c": [
      "Class E that begins right at the surface of the airport",
      "Class E starting at 700 ft AGL, not at the surface",
      "Class B airspace requiring a clearance before entry",
      "A restricted area that is closed during published hours"
    ],
    "a": 1,
    "e": "The vignette marks Class E from 700 ft AGL, while a dashed magenta line marks Class E to the surface.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Symbols",
    "q": "To tell whether your site sits under a Class B shelf, read the:",
    "c": [
      "Terrain tint, which shows how high the ground rises under the shelf",
      "Floor and ceiling numbers printed along that segment",
      "Airport elevation figure printed next to the primary airport symbol",
      "Compass rose drawn around the nearest navigation aid on the chart"
    ],
    "a": 1,
    "e": "Each Class B segment lists its floor and ceiling, telling you whether your site is beneath the shelf.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Special Use",
    "q": "The controlling agency for a charted restricted area is listed:",
    "c": [
      "Nowhere on the chart; it must be requested by radio",
      "In the special use airspace tabulation on the chart",
      "On the compass rose drawn near the navigation aids",
      "In the airport data block next to the nearest airport"
    ],
    "a": 1,
    "e": "The margin tabulation lists each special use area's altitudes, times, and controlling agency.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Obstacles",
    "q": "For a charted group of obstacles, the printed height refers to:",
    "c": [
      "The nearest airport",
      "The shortest one",
      "The tallest obstacle in the group",
      "The average height"
    ],
    "a": 2,
    "e": "A grouped obstacle symbol lists the height of the tallest obstacle in the cluster.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Navigation",
    "q": "Reading latitude and longitude off a sectional is useful for:",
    "c": [
      "Finding the control tower frequency for the nearest airport",
      "Measuring the surface wind speed across the charted area",
      "Entering a precise location into a flight planning app",
      "Judging the height of the cloud base above the terrain"
    ],
    "a": 2,
    "e": "The latitude and longitude grid lets a pilot enter an exact site location into planning tools.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Landmarks",
    "q": "Prominent features like water tanks and stadiums are charted because they:",
    "c": [
      "Reliably indicate the wind direction at the surface",
      "Indicate the class of airspace overlying the area",
      "Serve as visual landmarks and may be obstacles",
      "Mark the locations of approved aircraft fuel stops"
    ],
    "a": 2,
    "e": "Distinctive structures help with visual navigation and can also be flight obstacles.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Elevation",
    "q": "A Maximum Elevation Figure printed as '27' represents:",
    "c": [
      "27 ft AGL",
      "2,700 ft MSL",
      "27 nautical miles",
      "270 ft MSL"
    ],
    "a": 1,
    "e": "The MEF is in hundreds of feet MSL, so 27 means 2,700 ft.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Navigation",
    "q": "Converting a true course to a magnetic course requires applying:",
    "c": [
      "The airport elevation read from the nearest data block",
      "The magnetic variation shown by isogonic lines",
      "The Maximum Elevation Figure for that chart quadrangle",
      "The forecast wind speed and direction along the route"
    ],
    "a": 1,
    "e": "Magnetic variation, read from isogonic lines, converts between true and magnetic course.",
    "acs": "UA.II.A"
  },
  {
    "b": "Loading",
    "s": "Performance",
    "q": "Adding payload to a multirotor raises the:",
    "c": [
      "Power needed just to hover",
      "Battery capacity",
      "Maximum altitude",
      "Legal weight limit"
    ],
    "a": 0,
    "e": "Extra weight increases the power required to hover, which drains the battery faster.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Securing Payload",
    "q": "A payload should be secured before flight so that it:",
    "c": [
      "Cannot shift and change the center of gravity in flight",
      "Looks neat and presentable in any photographs taken of the aircraft",
      "Increases the total takeoff weight to improve stability in gusty wind",
      "Adds aerodynamic drag that slows the aircraft to a safer cruise speed"
    ],
    "a": 0,
    "e": "A loose payload can shift in flight, moving the center of gravity and destabilizing the aircraft.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Center of Gravity",
    "q": "If a payload comes loose and slides during flight, the likely result is:",
    "c": [
      "A shifting center of gravity and degraded control",
      "Improved efficiency from the lower overall center of mass",
      "A higher top speed as the load redistributes toward the rear",
      "Longer flight time because the motors share the load evenly"
    ],
    "a": 0,
    "e": "A payload sliding in flight moves the center of gravity and makes the aircraft harder to control.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Performance",
    "q": "Removing unnecessary payload before a flight will generally:",
    "c": [
      "Improve climb and extend flight time",
      "Reduce stability",
      "Have no effect",
      "Noticeably shorten the total flight time"
    ],
    "a": 0,
    "e": "Less weight means less power needed, improving climb and lengthening flight time.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Endurance",
    "q": "Fitting a heavier camera means a pilot should plan for:",
    "c": [
      "Longer endurance because the extra mass smooths out the flight",
      "Shorter flight time and more frequent battery swaps",
      "A higher safe operating ceiling above the usual altitude limit",
      "No change in planning, since the flight controller compensates"
    ],
    "a": 1,
    "e": "A heavier payload cuts endurance, so plan shorter legs and more battery changes.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Density Altitude",
    "q": "At a high-elevation site on a warm day, a good practice is to:",
    "c": [
      "Add the maximum payload to improve overall stability",
      "Test a hover before committing to the full mission",
      "Assume normal sea-level performance for planning",
      "Skip the preflight check to launch before it warms up"
    ],
    "a": 1,
    "e": "High density altitude cuts performance, so confirm a stable hover before flying the mission.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Wind",
    "q": "Flying with both a payload and strong wind will:",
    "c": [
      "Improve hover efficiency",
      "Extend the range",
      "Have no real combined effect on the flight at all",
      "Drain the battery faster and reduce range"
    ],
    "a": 3,
    "e": "Payload and wind both raise power demand, so together they cut range and endurance sharply.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Preflight",
    "q": "A test hover just after takeoff lets a pilot confirm:",
    "c": [
      "The current weather forecast for the remainder of the planned flight",
      "The class of airspace that overlies the launch site before climbing",
      "The aircraft is balanced and handling normally with its load",
      "The aircraft registration number is correctly displayed on the airframe"
    ],
    "a": 2,
    "e": "A brief test hover verifies the load is balanced and the aircraft handles normally before the mission.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Weight Distribution",
    "q": "To keep the center of gravity within limits, payload should be:",
    "c": [
      "Placed wherever convenient",
      "Mounted as far forward as possible",
      "Hung from one arm",
      "Distributed so the load is centered and balanced"
    ],
    "a": 3,
    "e": "Centering and balancing the payload keeps the center of gravity within the aircraft's limits.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Battery",
    "q": "Planning for cold-weather flights, a pilot should:",
    "c": [
      "Carry spare batteries and expect reduced capacity",
      "Overload to compensate",
      "Expect longer flight times",
      "Leave packs in the cold to save them"
    ],
    "a": 0,
    "e": "Cold lowers usable capacity, so carry spares and plan for shorter flights.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Performance",
    "q": "An overloaded drone may be unable to:",
    "c": [
      "Climb out of ground effect",
      "Connect to the controller",
      "Display its battery level",
      "Power on"
    ],
    "a": 0,
    "e": "Too much weight can leave a drone unable to climb out of ground effect into stable flight.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Battery",
    "q": "The best way to store lithium batteries between flights is:",
    "c": [
      "Fully charged in a hot car",
      "At a partial charge in a cool, dry place",
      "Fully depleted for weeks",
      "In direct sunlight"
    ],
    "a": 1,
    "e": "Lithium packs last longest stored at a partial charge in a cool, dry location.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Regulations",
    "s": "Currency",
    "q": "To stay current, how often must a remote PIC complete recurrent training?",
    "c": [
      "Every 6 months",
      "Only once after the initial test",
      "Every 24 calendar months",
      "Every 12 calendar months"
    ],
    "a": 2,
    "e": "Part 107 currency requires completing the free online recurrent training every 24 calendar months.",
    "acs": "UA.I.C"
  },
  {
    "b": "Regulations",
    "s": "Operating Limitations",
    "q": "What is the maximum groundspeed allowed for a small UAS under Part 107?",
    "c": [
      "100 knots",
      "100 mph (87 knots)",
      "87 mph",
      "120 mph"
    ],
    "a": 1,
    "e": "Part 107 limits groundspeed to 100 mph, which is 87 knots.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Operating Limitations",
    "q": "What is the minimum flight visibility from the control station under Part 107?",
    "c": [
      "5 statute miles",
      "1 statute mile",
      "3 statute miles",
      "3 nautical miles"
    ],
    "a": 2,
    "e": "Part 107 requires at least 3 statute miles of flight visibility from the control station.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Visual Observer",
    "q": "When a visual observer is used, the remote PIC and VO must be able to do what?",
    "c": [
      "Both wear FPV goggles",
      "Communicate with each other at all times",
      "Each hold a separate certificate",
      "Stay at least one mile apart"
    ],
    "a": 1,
    "e": "The remote PIC and visual observer must maintain effective communication throughout the operation.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Remote ID",
    "q": "A drone without Remote ID capability may generally only be flown where?",
    "c": [
      "Anywhere below 400 ft AGL",
      "Within an FAA-Recognized Identification Area (FRIA)",
      "Only over private property",
      "Within 5 miles of the operator's home"
    ],
    "a": 1,
    "e": "Aircraft without Remote ID must operate within an FAA-Recognized Identification Area.",
    "acs": "UA.I.F"
  },
  {
    "b": "Airspace",
    "s": "Authorization",
    "q": "To fly in Class B, C, or D airspace under Part 107, a remote pilot must have what?",
    "c": [
      "Prior ATC authorization",
      "An instrument rating",
      "A Mode C transponder",
      "Nothing below 400 ft"
    ],
    "a": 0,
    "e": "Operations in controlled airspace such as Class B, C, and D require prior ATC authorization.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "LAANC",
    "q": "Through LAANC, a remote pilot can receive authorization to fly up to what altitude?",
    "c": [
      "Unlimited altitude, as long as it stays clear of clouds",
      "1,200 feet AGL everywhere within controlled airspace",
      "The ceiling shown on the UAS Facility Map grid",
      "Always 400 feet AGL, anywhere in controlled airspace"
    ],
    "a": 2,
    "e": "LAANC grants near-real-time authorization up to the grid ceiling on the UAS Facility Map.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "Class E Surface",
    "q": "Operating in surface-based Class E airspace around an airport requires what?",
    "c": [
      "A filed flight plan",
      "ATC authorization",
      "Only a transponder",
      "No authorization since Class E is uncontrolled"
    ],
    "a": 1,
    "e": "Surface-based Class E around an airport is controlled and requires ATC authorization.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "TFR",
    "q": "Where should a remote pilot check for active Temporary Flight Restrictions?",
    "c": [
      "Only the sectional chart",
      "The aircraft maintenance manual",
      "FAA NOTAMs and tfr.faa.gov",
      "TFRs do not apply to drones"
    ],
    "a": 2,
    "e": "Active TFRs are published through FAA NOTAMs and at tfr.faa.gov and must be checked before flight.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Special Flight Rules",
    "q": "Before flying, a remote pilot learns of a Restricted Area along the route. What is the best action?",
    "c": [
      "Fly through it at night",
      "Confirm its status and avoid it unless authorized",
      "Ignore it because drones are exempt",
      "Fly through it below 400 ft"
    ],
    "a": 1,
    "e": "Verify the area's status and stay clear unless the controlling agency authorizes entry.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Symbols",
    "q": "On a sectional chart, a solid blue line around an airport depicts what airspace?",
    "c": [
      "Class E surface",
      "Class D",
      "Class B",
      "Class C"
    ],
    "a": 2,
    "e": "Solid blue lines on a sectional depict Class B airspace boundaries.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Symbols",
    "q": "On a sectional chart, a solid magenta line around an airport depicts what airspace?",
    "c": [
      "Class C",
      "Class B",
      "Class D",
      "Class G"
    ],
    "a": 0,
    "e": "Solid magenta lines on a sectional depict Class C airspace.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Symbols",
    "q": "On a sectional chart, a segmented (dashed) blue line around an airport depicts what airspace?",
    "c": [
      "Class B",
      "Class E surface",
      "Class C",
      "Class D"
    ],
    "a": 3,
    "e": "A segmented blue line depicts Class D airspace.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Navigation",
    "q": "Lines of latitude (parallels) on a sectional chart run in what direction?",
    "c": [
      "East to west, measuring position north or south",
      "North to south, measuring east or west",
      "Diagonally across the chart",
      "They show magnetic variation"
    ],
    "a": 0,
    "e": "Parallels of latitude run east-west and measure how far north or south a point lies.",
    "acs": "UA.II.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "In a METAR reporting '28012KT', what is being described?",
    "c": [
      "Altimeter setting 280",
      "Visibility of 280 at 12",
      "Wind from 280 degrees at 12 knots",
      "Temperature 28 dewpoint 12"
    ],
    "a": 2,
    "e": "In a METAR, '28012KT' means the wind is from 280 degrees at 12 knots.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "Density Altitude",
    "q": "How does high density altitude affect a small multirotor?",
    "c": [
      "It has no effect on electric aircraft",
      "It reduces rotor thrust and degrades performance",
      "It improves climb performance",
      "It increases battery capacity"
    ],
    "a": 1,
    "e": "High density altitude thins the air, reducing rotor thrust and overall performance.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Wind Shear",
    "q": "Why is wind shear hazardous to a small UAS?",
    "c": [
      "It steadily improves aircraft stability by smoothing out gusts near the ground",
      "It only occurs above 10,000 feet, well outside the Part 107 altitude limit",
      "It is always visible to the pilot as a clear line of clouds or blowing dust",
      "It is a sudden change in wind over a short distance that can upset control"
    ],
    "a": 3,
    "e": "Wind shear is an abrupt change in wind speed or direction over a short distance and can cause loss of control.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Fronts",
    "q": "The passage of a cold front is most often associated with what?",
    "c": [
      "Gusty winds and a risk of thunderstorms",
      "No change in weather",
      "Days of steady light rain",
      "Guaranteed clearing and calm winds"
    ],
    "a": 0,
    "e": "Cold front passage commonly brings gusty winds, rapid weather changes, and thunderstorms.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Stability",
    "q": "A stable atmosphere is generally indicated by what?",
    "c": [
      "Stratiform clouds and smooth air",
      "Gusty winds and excellent visibility",
      "Towering cumulus and turbulence",
      "Frequent thunderstorms"
    ],
    "a": 0,
    "e": "Stable air tends to produce stratiform clouds, steady conditions, and smooth flying.",
    "acs": "UA.III.B"
  },
  {
    "b": "Operations",
    "s": "Lost Link",
    "q": "A sound lost-link procedure should cause the aircraft to do what?",
    "c": [
      "Hand control to the nearest bystander on the ground",
      "Perform a predictable action such as return-to-home or land",
      "Continue the planned mission on its own until the battery dies",
      "Immediately cut power to all motors and drop straight to the ground"
    ],
    "a": 1,
    "e": "On lost link the aircraft should perform a predictable, preprogrammed safe action like return-to-home or a controlled landing.",
    "acs": "UA.V.C"
  },
  {
    "b": "Operations",
    "s": "CRM",
    "q": "Effective crew resource management mainly improves what?",
    "c": [
      "Maximum aircraft speed during the cruise portion of flight",
      "Communication and workload sharing among the crew",
      "Battery life by coordinating the power used by each system",
      "Camera resolution by stabilizing the aircraft in the air"
    ],
    "a": 1,
    "e": "Crew resource management focuses on clear communication and distributing workload to reduce error.",
    "acs": "UA.V.D"
  },
  {
    "b": "Loading",
    "s": "Maximum Weight",
    "q": "Part 107 applies to small unmanned aircraft weighing how much?",
    "c": [
      "Less than 10 pounds",
      "Less than 25 pounds",
      "Less than 55 pounds including payload",
      "Less than a full 100 pounds in total weight"
    ],
    "a": 2,
    "e": "A small unmanned aircraft under Part 107 weighs less than 55 pounds including everything on board.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Voltage Sag",
    "q": "Under heavy current draw, battery voltage sag can cause what?",
    "c": [
      "A stronger and faster GPS lock when the aircraft powers on",
      "A higher payload capacity for the remainder of the flight",
      "Longer total flight time because the pack runs cooler",
      "Premature low-voltage warnings and reduced power"
    ],
    "a": 3,
    "e": "Heavy current draw causes voltage sag, which can trigger early low-battery cutoffs and loss of power.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Weight Distribution",
    "q": "For the best handling, how should payload be mounted?",
    "c": [
      "Loosely so it can move freely",
      "Centered near the CG and firmly secured",
      "On one side to balance the motor",
      "As far forward as possible"
    ],
    "a": 1,
    "e": "Mount payload near the center of gravity and secure it so the CG does not shift in flight.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Endurance",
    "q": "What are the biggest factors reducing an electric multirotor's flight time?",
    "c": [
      "Excess weight and headwinds",
      "Airframe color",
      "Number of GPS satellites",
      "Camera megapixels"
    ],
    "a": 0,
    "e": "Total weight and wind are the main drivers of reduced multirotor endurance.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Manufacturer Limits",
    "q": "Where is the maximum payload weight for your aircraft found?",
    "c": [
      "Printed on the sectional aeronautical chart",
      "In the METAR",
      "In the manufacturer's published limits",
      "In 14 CFR Part 107"
    ],
    "a": 2,
    "e": "Always follow the manufacturer's published weight and payload limits for your specific aircraft.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Regulations",
    "s": "Carriage of Property",
    "q": "Under Part 107, carrying property for compensation is treated how?",
    "c": [
      "Allowed only across state lines as interstate commerce under the rules",
      "Permitted within a state, with aircraft and payload under 55 lb",
      "Allowed up to 100 lb total as long as no hazardous materials are aboard",
      "Prohibited in all cases, since Part 107 does not allow carrying property"
    ],
    "a": 1,
    "e": "Part 107 allows transporting property for compensation within a state as long as the aircraft and payload weigh under 55 lb.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Dropping Objects",
    "q": "Dropping or dispensing an object from a small UAS is handled how under Part 107?",
    "c": [
      "Allowed only at night with anti-collision lighting on the aircraft",
      "Allowed only over open water that is clear of vessels and swimmers",
      "Permitted if it creates no undue hazard to persons or property",
      "Always prohibited under Part 107, regardless of the precautions taken"
    ],
    "a": 2,
    "e": "Part 107 permits dropping objects provided no undue hazard is created to persons or property.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Careless Operation",
    "q": "Operating a small UAS in a careless or reckless manner is what under Part 107?",
    "c": [
      "Allowed over private land",
      "Prohibited",
      "Allowed below 100 ft AGL",
      "Allowed with any waiver"
    ],
    "a": 1,
    "e": "Part 107 prohibits careless or reckless operation that could endanger life or property.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Single Remote PIC",
    "q": "How many small unmanned aircraft may one person operate at the same time under Part 107?",
    "c": [
      "Up to three",
      "Up to five",
      "One",
      "Unlimited with a waiver"
    ],
    "a": 2,
    "e": "A remote PIC may operate only one small unmanned aircraft at a time.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Over Vehicles",
    "q": "Operating a small UAS from a moving vehicle is allowed only under what condition?",
    "c": [
      "Only on private roads",
      "Never, in any case",
      "Only over a sparsely populated area",
      "Anywhere below 400 ft AGL"
    ],
    "a": 2,
    "e": "Part 107 permits operating from a moving vehicle only over sparsely populated areas.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Preflight",
    "q": "What must the remote PIC do before each flight regarding the aircraft?",
    "c": [
      "Notify the local police department of the planned flight in advance",
      "Inspect it to ensure it is in a condition for safe operation",
      "File a detailed flight plan with air traffic control before launch",
      "Inspect it only once per week, regardless of how often it flies"
    ],
    "a": 1,
    "e": "The remote PIC must conduct a preflight inspection to confirm the aircraft is in a condition for safe operation.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "FAA Inspection",
    "q": "Who must make a small UAS available to the FAA for inspection or testing on request?",
    "c": [
      "Only the manufacturer that originally built and sold the aircraft",
      "Only the local airport manager where the drone is normally based",
      "No one, because the FAA cannot inspect privately owned drones",
      "The remote PIC, owner, or person manipulating the controls"
    ],
    "a": 3,
    "e": "The remote PIC, owner, or controlling person must make the aircraft available to the FAA for inspection or testing.",
    "acs": "UA.I.A"
  },
  {
    "b": "Airspace",
    "s": "MOA",
    "q": "How is a Military Operations Area (MOA) depicted on a sectional chart?",
    "c": [
      "A solid green tint",
      "A magenta hatched (brushed) boundary",
      "A solid blue line",
      "A segmented, dashed blue boundary line"
    ],
    "a": 1,
    "e": "MOAs are shown on sectionals with a magenta hatched boundary.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Warning Area",
    "q": "Where is a Warning Area located?",
    "c": [
      "Only directly over airports",
      "Only over mountainous terrain",
      "Beginning 3 NM outward from the U.S. coast",
      "Over the center of the country"
    ],
    "a": 2,
    "e": "Warning Areas begin 3 nautical miles off the U.S. coast and may contain hazards to flight.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "UAS Facility Map",
    "q": "Where do you find the maximum altitude you can request via LAANC for a location?",
    "c": [
      "The METAR",
      "The aircraft manual",
      "The chart legend only",
      "The UAS Facility Maps (UASFM)"
    ],
    "a": 3,
    "e": "UAS Facility Maps show the maximum altitudes available for LAANC authorization in each grid.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "Authorization Source",
    "q": "What are the two FAA channels for airspace authorization?",
    "c": [
      "ATIS for recorded conditions and AWOS for automated weather",
      "A phone call and an email sent directly to the control tower",
      "LAANC for near-real-time and DroneZone for manual requests",
      "The drone manufacturer and the Federal Communications Commission"
    ],
    "a": 2,
    "e": "Authorization is obtained through LAANC for near-real-time requests or the FAA DroneZone portal for manual requests.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "Controlled Firing Area",
    "q": "How does a Controlled Firing Area differ from other special use airspace?",
    "c": [
      "It is charted in solid blue rather than the usual hatched lines",
      "It is always active and closed to all civil aircraft at all times",
      "It requires a LAANC authorization before any drone may enter",
      "Activities stop when an aircraft is detected approaching"
    ],
    "a": 3,
    "e": "A Controlled Firing Area suspends its activity when an aircraft is detected approaching, so it is not charted.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Symbols",
    "q": "A faded magenta band (vignette) around an airport on a sectional indicates what?",
    "c": [
      "Class B airspace",
      "Class D airspace",
      "Class E airspace beginning at 700 ft AGL",
      "Class E airspace beginning right at the surface"
    ],
    "a": 2,
    "e": "A faded magenta vignette marks Class E airspace that begins at 700 ft AGL.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Symbols",
    "q": "A faded blue band (vignette) on a sectional indicates what?",
    "c": [
      "Class A airspace at and above 18,000 ft",
      "Class E airspace beginning at the surface",
      "Class E airspace beginning at 1,200 ft AGL",
      "Class C airspace surrounding a busy primary airport"
    ],
    "a": 2,
    "e": "A faded blue vignette marks Class E airspace that begins at 1,200 ft AGL.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Scale",
    "q": "On a sectional chart, one minute of latitude equals what distance?",
    "c": [
      "One statute mile",
      "One nautical mile",
      "Ten nautical miles",
      "One kilometer"
    ],
    "a": 1,
    "e": "One minute of latitude equals one nautical mile, which is useful for measuring distance on a sectional.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Elevation",
    "q": "What does the Maximum Elevation Figure (MEF) in a chart quadrangle tell you?",
    "c": [
      "The height of the lowest cloud base reported in the area",
      "The magnetic variation to apply when navigating by compass",
      "The field elevation of the primary airport in that quadrant",
      "The highest terrain or obstacle in that quadrant in MSL"
    ],
    "a": 3,
    "e": "The Maximum Elevation Figure shows the highest known terrain or obstacle in that quadrant, in MSL.",
    "acs": "UA.II.B"
  },
  {
    "b": "Weather",
    "s": "Inversion",
    "q": "What is a likely effect of a temperature inversion?",
    "c": [
      "Strong vertical updrafts",
      "Stable air with reduced visibility near the surface",
      "Greatly improved visibility",
      "Severe turbulence and widespread heavy thunderstorms"
    ],
    "a": 1,
    "e": "A temperature inversion creates stable air that can trap haze and moisture, reducing visibility near the surface.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Fog",
    "q": "Fog is most likely to form under which conditions?",
    "c": [
      "Rapidly rising pressure with gusty winds",
      "Large spread with strong, steady surface wind",
      "Small temperature-dewpoint spread and light wind",
      "Clear, hot, and very dry air right at the surface"
    ],
    "a": 2,
    "e": "Fog forms when the air cools to near the dewpoint with a small temperature-dewpoint spread and light wind.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "TAF",
    "q": "What does a TAF forecast cover?",
    "c": [
      "The entire country in a single combined national outlook",
      "Pilot-reported turbulence collected from aircraft in the area",
      "Wind direction only, with no information on clouds or visibility",
      "Conditions within about 5 statute miles of an airport"
    ],
    "a": 3,
    "e": "A TAF is a Terminal Aerodrome Forecast covering the area within about 5 statute miles of an airport.",
    "acs": "UA.III.A"
  },
  {
    "b": "Operations",
    "s": "Hazardous Attitudes",
    "q": "Which thought reflects the hazardous attitude of invulnerability?",
    "c": [
      "The rules do not matter",
      "I must act now",
      "I can handle anything",
      "It will not happen to me"
    ],
    "a": 3,
    "e": "Believing an accident will not happen to me is the invulnerability attitude; the antidote is that it could happen to me.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Personal Minimums",
    "q": "How does a personal minimums checklist help a remote pilot?",
    "c": [
      "It logs every maintenance action performed on the aircraft over its service life",
      "It increases the aircraft's top speed during routine operations",
      "It sets safety limits in advance to resist in-the-moment pressure",
      "It replaces the preflight inspection on familiar flights"
    ],
    "a": 2,
    "e": "Personal minimums set safety limits ahead of time so decisions are not driven by pressure in the moment.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Bystander Safety",
    "q": "What is the safest practice regarding nonparticipating people during a flight?",
    "c": [
      "Only announce your presence by radio",
      "Fly over them only at night",
      "Keep them clear of the operating area",
      "Fly directly over them for coverage"
    ],
    "a": 2,
    "e": "Keep people who are not part of the operation clear of the area unless your operation is specifically approved to fly over people.",
    "acs": "UA.V.D"
  },
  {
    "b": "Loading",
    "s": "Battery Health",
    "q": "What should be done with a swollen lithium-polymer battery?",
    "c": [
      "Remove it from service and dispose of it safely",
      "Fully charge it and reuse it",
      "Keep on flying it until it finally fails completely",
      "Puncture it to release the gas"
    ],
    "a": 0,
    "e": "A swollen LiPo battery is damaged and unsafe, so remove it from service and dispose of it properly.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Battery",
    "q": "What can charging a battery beyond its rated voltage cause?",
    "c": [
      "Longer flight time",
      "No effect at all",
      "A safe increase in capacity",
      "Overheating, damage, or fire"
    ],
    "a": 3,
    "e": "Overcharging a battery past its rated voltage risks overheating, damage, and fire.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Propellers",
    "q": "What can an unbalanced propeller cause?",
    "c": [
      "Longer flight time because the blade moves through the air more freely",
      "Improved stability and smoother handling in gusty wind",
      "Better GPS accuracy from the steadier platform that it creates",
      "Vibration that blurs imagery and stresses motors and the airframe"
    ],
    "a": 3,
    "e": "An unbalanced propeller causes vibration that degrades imagery and stresses the motors and airframe.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Gusts",
    "q": "How does flying in gusty wind affect the aircraft?",
    "c": [
      "It increases power demand and reduces control and endurance",
      "It increases the battery's usable capacity for that flight",
      "It improves stability by holding the airframe steady in the air",
      "It raises the maximum payload the aircraft can safely carry"
    ],
    "a": 0,
    "e": "Gusty wind makes the aircraft work harder, increasing power demand while reducing control and endurance.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Payload",
    "q": "What is the effect of reducing payload weight?",
    "c": [
      "Increased power draw",
      "Improved endurance and maneuverability",
      "A permanently lower resting battery voltage",
      "Reduced stability"
    ],
    "a": 1,
    "e": "Carrying less weight reduces power demand, improving endurance and maneuverability.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Securing Payload",
    "q": "When mounting an external camera or gimbal, what should you do?",
    "c": [
      "Stay within the rated payload and keep the CG centered",
      "Mount it as far from center as possible",
      "Leave it loose for flexibility",
      "Exceed the rated payload for better footage"
    ],
    "a": 0,
    "e": "Keep any added camera or gimbal within the rated payload and near the center of gravity, and secure it.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Humidity",
    "q": "How does high humidity affect aircraft performance?",
    "c": [
      "It increases the lift the rotors produce",
      "It improves the battery's power output",
      "It cannot have any measurable effect on performance",
      "It slightly lowers air density and performance"
    ],
    "a": 3,
    "e": "High humidity slightly reduces air density, which can modestly reduce performance.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Battery Health",
    "q": "What is a reliable sign a battery should be retired from service?",
    "c": [
      "Swelling, physical damage, or failure to hold a charge",
      "Its brand name, since some brands are rated for fewer cycles",
      "Its age in days alone, regardless of how it has performed",
      "Its color, which fades as the cells gradually wear out"
    ],
    "a": 0,
    "e": "Swelling, physical damage, or an inability to hold a charge means a battery should be retired.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Regulations",
    "s": "Waivers",
    "q": "What does a Part 107 Certificate of Waiver allow?",
    "c": [
      "Ignoring all airspace authorization rules near controlled airports",
      "Flying aircraft of any weight, including those above the 55 lb limit",
      "Deviating from specific operating rules when safety is demonstrated",
      "Skipping the initial knowledge test required for the remote certificate"
    ],
    "a": 2,
    "e": "A waiver lets you deviate from certain Part 107 rules when you show the operation can be conducted safely.",
    "acs": "UA.I.D"
  },
  {
    "b": "Regulations",
    "s": "Ops Over People",
    "q": "Part 107 operations over people are divided into how many categories?",
    "c": [
      "None, it is banned outright",
      "Ten categories",
      "Four categories based on injury risk",
      "Two categories"
    ],
    "a": 2,
    "e": "Operations over people fall into four categories defined by the injury risk the aircraft poses.",
    "acs": "UA.I.E"
  },
  {
    "b": "Regulations",
    "s": "Night Operations",
    "q": "To operate at night under Part 107, the aircraft must have what?",
    "c": [
      "Anti-collision lighting visible for at least 3 statute miles",
      "A strobe light that is visible for at least 1 statute mile",
      "Landing lights only, pointed downward toward the takeoff area",
      "No special equipment beyond what daytime operations require"
    ],
    "a": 0,
    "e": "Night operations require anti-collision lighting visible for at least 3 statute miles.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Night Training",
    "q": "Since the 2021 rule update, what is required to fly at night?",
    "c": [
      "An instrument rating",
      "Two visual observers",
      "Completing the required training, no waiver needed",
      "A separate night waiver in all cases"
    ],
    "a": 2,
    "e": "Night operations are allowed after completing the required training and using anti-collision lighting; a waiver is no longer needed.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Registration Marking",
    "q": "Where must the aircraft registration number be displayed?",
    "c": [
      "Filed only with the local police department",
      "Only stored on a phone",
      "On the controller screen",
      "On the exterior surface of the aircraft"
    ],
    "a": 3,
    "e": "The registration number must be legibly marked on the exterior surface of the aircraft.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Operating Limitations",
    "q": "What must the remote PIC maintain with the aircraft throughout the flight?",
    "c": [
      "A chase vehicle",
      "Continuous radio contact with ATC",
      "Visual line of sight",
      "A filed IFR flight plan"
    ],
    "a": 2,
    "e": "The remote PIC or a visual observer must keep the aircraft within visual line of sight throughout the operation.",
    "acs": "UA.I.B"
  },
  {
    "b": "Airspace",
    "s": "Chart Currency",
    "q": "On what cycle are VFR sectional charts generally updated?",
    "c": [
      "Every 10 years",
      "They are never updated",
      "Every day",
      "About every 56 days"
    ],
    "a": 3,
    "e": "VFR sectional charts are generally updated on a 56-day cycle, so always use a current chart.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Stadium TFR",
    "q": "Near a large sporting event, flight is restricted within what area?",
    "c": [
      "3 NM and below 3,000 ft AGL around the stadium",
      "There is no restriction for drones",
      "10 NM only",
      "1 NM only"
    ],
    "a": 0,
    "e": "A standing stadium TFR restricts flight within 3 NM and below 3,000 ft AGL from one hour before to one hour after large sporting events.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "Special Flight Rules",
    "q": "How is the Washington, DC area classified for UAS operations?",
    "c": [
      "A Special Flight Rules Area with strict restrictions",
      "Unrestricted airspace below 400 feet above the ground at all times",
      "Open Class G airspace just like most rural areas of the country",
      "A standard Military Operations Area with published hours"
    ],
    "a": 0,
    "e": "The Washington, DC area is a Special Flight Rules Area where drone flight is heavily restricted or prohibited.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airways",
    "q": "How are Victor airways depicted on a sectional chart?",
    "c": [
      "Magenta hatched bands",
      "Solid red lines",
      "Green dashed lines",
      "Light blue lines"
    ],
    "a": 3,
    "e": "Victor airways are charted as light blue lines marking low-altitude federal airways.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Visual Checkpoint",
    "q": "How is a visual checkpoint shown on a sectional chart?",
    "c": [
      "A blue star",
      "A green square",
      "A magenta flag symbol",
      "A red circle"
    ],
    "a": 2,
    "e": "Visual checkpoints are marked with a magenta flag symbol on sectionals.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Terrain",
    "q": "What do contour lines on a sectional chart represent?",
    "c": [
      "Airspace boundaries",
      "Lines of equal terrain elevation",
      "Wind direction",
      "Federal airways"
    ],
    "a": 1,
    "e": "Contour lines connect points of equal terrain elevation to show relief.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Legend",
    "q": "What is the chart legend used for?",
    "c": [
      "Getting the current weather conditions for the charted region",
      "Finding the exact publication and expiration date of the chart",
      "Automatically plotting a flight route between two airports",
      "Interpreting the chart's symbols, colors, and abbreviations"
    ],
    "a": 3,
    "e": "The legend explains the symbols, colors, and abbreviations used on the sectional chart.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Landmarks",
    "q": "How are cities and towns depicted on a sectional chart?",
    "c": [
      "As yellow-tinted areas",
      "As red X marks",
      "As green bands",
      "As blue circles"
    ],
    "a": 0,
    "e": "Cities and towns appear as yellow-tinted areas, which helps identify congested areas to avoid.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Navigation",
    "q": "Which chart lines run true north and south?",
    "c": [
      "Lines of longitude (meridians)",
      "Contour lines",
      "Victor airways",
      "Isogonic magnetic variation lines"
    ],
    "a": 0,
    "e": "Meridians of longitude run true north-south and indicate true north on the chart.",
    "acs": "UA.II.A"
  },
  {
    "b": "Weather",
    "s": "Convection",
    "q": "What do convective currents on a hot afternoon typically cause?",
    "c": [
      "Smooth, stable air",
      "Low-level turbulence and bumpy air",
      "Widespread fog",
      "Noticeably higher surface air density"
    ],
    "a": 1,
    "e": "Surface heating creates rising convective currents that cause low-level turbulence.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Microburst",
    "q": "Why is a microburst hazardous?",
    "c": [
      "It brings gentle, steady winds that push the aircraft off its course",
      "It produces intense localized downdrafts and sudden wind shifts",
      "It clears the skies and sharply improves visibility near the surface",
      "It improves lift across the rotors, causing an unexpected fast climb"
    ],
    "a": 1,
    "e": "A microburst is a small, intense downdraft with sudden severe wind shifts that can overpower an aircraft.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Atmosphere",
    "q": "In which atmospheric layer does nearly all weather occur?",
    "c": [
      "The troposphere",
      "The mesosphere",
      "The exosphere",
      "The stratosphere"
    ],
    "a": 0,
    "e": "Nearly all weather, including clouds and turbulence, occurs in the troposphere.",
    "acs": "UA.III.B"
  },
  {
    "b": "Operations",
    "s": "Go No-Go",
    "q": "When should a go/no-go decision be made?",
    "c": [
      "Before each flight, based on conditions and readiness",
      "Only when the client specifically asks for one to be made",
      "Only once per month, covering all flights in that period",
      "After takeoff, once the aircraft is already in the air"
    ],
    "a": 0,
    "e": "Make a go/no-go decision before every flight based on weather, aircraft, and pilot readiness.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "VLOS",
    "q": "If you lose visual line of sight of the aircraft, what should you do?",
    "c": [
      "Ignore it entirely as long as the battery still shows a full charge",
      "Regain it or execute a safe recovery such as return-to-home",
      "Keep flying normally using only the onboard video feed",
      "Increase speed and fly around to try to locate it"
    ],
    "a": 1,
    "e": "If you lose visual line of sight you must regain it or begin a safe recovery such as return-to-home.",
    "acs": "UA.I.B"
  },
  {
    "b": "Loading",
    "s": "Maneuverability",
    "q": "What does increased weight do to climb and maneuvering?",
    "c": [
      "Reduces climb rate and maneuvering margin",
      "Improves battery temperature",
      "Increases climb rate",
      "Sharpens GPS accuracy"
    ],
    "a": 0,
    "e": "Added weight reduces climb rate and the margin available for maneuvering.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Propellers",
    "q": "What happens if a propeller is installed in the wrong position or rotation?",
    "c": [
      "It only reduces motor noise without affecting how the aircraft handles",
      "It fails to produce proper lift and can cause loss of control",
      "It extends total flight time because the motors share the load more evenly",
      "It improves overall efficiency by balancing thrust across the four arms"
    ],
    "a": 1,
    "e": "A propeller in the wrong position or rotation will not produce proper lift and can cause loss of control.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Securing Payload",
    "q": "Why does securing a payload matter in flight?",
    "c": [
      "A shifting load moves the CG and destabilizes the aircraft",
      "It has no real effect on a multirotor with four or more motors",
      "A fixed load increases battery life by smoothing the airflow",
      "A secured load improves handling by adding useful extra weight"
    ],
    "a": 0,
    "e": "An unsecured payload can shift in flight, moving the center of gravity and destabilizing the aircraft.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Voltage Sag",
    "q": "What does a battery voltage that drops quickly under throttle indicate?",
    "c": [
      "A GPS fault",
      "A propeller imbalance",
      "A fully healthy battery",
      "An aging or unhealthy battery"
    ],
    "a": 3,
    "e": "A rapid voltage drop under load indicates an aging or unhealthy battery that should be checked or retired.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Wind",
    "q": "What is the effect of flying at maximum payload in strong wind?",
    "c": [
      "It lowers the density altitude around the aircraft in flight",
      "It increases total flight time by smoothing out the airflow",
      "It improves stability because the extra weight resists gusts",
      "It significantly reduces endurance and safety margins"
    ],
    "a": 3,
    "e": "Combining maximum payload with strong wind sharply reduces endurance and safety margins.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Stability",
    "q": "What does a balanced, centered payload help with?",
    "c": [
      "Improving camera zoom",
      "Extending control range",
      "Increasing top speed only",
      "Maintaining predictable, stable flight"
    ],
    "a": 3,
    "e": "A balanced, centered payload keeps the CG within limits for predictable, stable flight.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Preflight",
    "q": "What should you confirm before adding any payload?",
    "c": [
      "That the battery has been removed and replaced with a fresh one",
      "That the GPS receiver is disabled to save power for the payload",
      "That the propellers have been removed before the payload goes on",
      "That it keeps the aircraft within weight and balance limits"
    ],
    "a": 3,
    "e": "Before adding payload, confirm it keeps the aircraft within its weight and balance limits.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Regulations",
    "s": "Currency",
    "q": "Since April 2021, how does a Part 107 pilot satisfy the recurrent currency requirement?",
    "c": [
      "By completing free online recurrent training",
      "By logging 10 flight hours",
      "By renewing the certificate every 2 years for a fee",
      "By passing a recurrent knowledge test at a testing center"
    ],
    "a": 0,
    "e": "Since April 6, 2021, recurrent currency is met with free online training, not a retest at a testing center.",
    "acs": "UA.I.C"
  },
  {
    "b": "Regulations",
    "s": "Registration",
    "q": "A small unmanned aircraft flown under Part 107 must be registered with the FAA",
    "c": [
      "only if flown in controlled airspace",
      "only if it carries a camera",
      "only if it weighs more than 0.55 lb",
      "individually, regardless of its weight"
    ],
    "a": 3,
    "e": "Every sUAS operated under Part 107 must be registered, regardless of weight.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Eligibility",
    "q": "What is the minimum age to be eligible for a remote pilot certificate with an sUAS rating?",
    "c": [
      "18 years old",
      "17 years old",
      "16 years old",
      "14 years old"
    ],
    "a": 2,
    "e": "An applicant for a remote pilot certificate must be at least 16 years old.",
    "acs": "UA.I.C"
  },
  {
    "b": "Regulations",
    "s": "Accident Reporting",
    "q": "An sUAS accident must be reported to the FAA if it causes at least serious injury, loss of consciousness, or property damage of more than",
    "c": [
      "$500",
      "$2,500",
      "$1,000",
      "$250"
    ],
    "a": 0,
    "e": "Report if there is serious injury, loss of consciousness, or property damage exceeding $500.",
    "acs": "UA.I.A"
  },
  {
    "b": "Regulations",
    "s": "Careless Operation",
    "q": "Operating a small unmanned aircraft in a careless or reckless manner so as to endanger life or property is",
    "c": [
      "allowed with a visual observer",
      "prohibited under Part 107",
      "allowed in Class G airspace",
      "allowed below 100 feet"
    ],
    "a": 1,
    "e": "Part 107 prohibits careless or reckless operation that endangers life or property.",
    "acs": "UA.I.B"
  },
  {
    "b": "Regulations",
    "s": "Waivers",
    "q": "The FAA will issue a Certificate of Waiver for a Part 107 operation when the applicant shows that",
    "c": [
      "the operation can be conducted safely under the terms of the waiver",
      "the drone weighs under 0.55 lb and is exempt from registration rules",
      "the operation will generate revenue for a registered commercial business",
      "the pilot has logged at least 100 hours as remote pilot in command"
    ],
    "a": 0,
    "e": "A waiver is issued when the applicant demonstrates the proposed operation can be conducted safely.",
    "acs": "UA.I.D"
  },
  {
    "b": "Regulations",
    "s": "Falsification",
    "q": "Falsifying or altering a record or report required under Part 107 is grounds for",
    "c": [
      "a verbal warning only",
      "suspension or revocation of the certificate",
      "a $50 fine",
      "no action at all if it was truly unintentional"
    ],
    "a": 1,
    "e": "Falsification, reproduction, or alteration of records is grounds for suspension or revocation of the certificate.",
    "acs": "UA.I.A"
  },
  {
    "b": "Regulations",
    "s": "Remote ID",
    "q": "Since September 2023, a drone that requires FAA registration generally must also",
    "c": [
      "carry a working transponder that reports its position to ATC",
      "file a flight plan with air traffic control before each flight",
      "be flown only in uncontrolled Class G airspace below 400 feet",
      "broadcast Remote ID information unless flown within a FRIA"
    ],
    "a": 3,
    "e": "Registered drones must broadcast Remote ID unless operated within an FAA-recognized identification area (FRIA).",
    "acs": "UA.I.F"
  },
  {
    "b": "Operations",
    "s": "Right-of-Way",
    "q": "Under Part 107, a small unmanned aircraft must yield the right of way to",
    "c": [
      "no other aircraft when in Class G",
      "only aircraft in controlled airspace",
      "all other aircraft",
      "only manned aircraft below 500 feet"
    ],
    "a": 2,
    "e": "Under 14 CFR 107.37, the sUAS must yield the right of way to all other aircraft.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "VLOS",
    "q": "When maintaining visual line of sight, which visual aid is allowed?",
    "c": [
      "Corrective lenses",
      "First-person-view goggles",
      "Binoculars",
      "A spotting scope"
    ],
    "a": 0,
    "e": "VLOS may be maintained only with corrective lenses, not binoculars or first-person-view goggles.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "CRM",
    "q": "Under Part 107, one person acting as remote PIC may operate",
    "c": [
      "only one small unmanned aircraft at a time",
      "up to three aircraft at once",
      "any number with a visual observer",
      "two aircraft if both are under 0.55 lb"
    ],
    "a": 0,
    "e": "A person may not act as remote PIC for more than one small unmanned aircraft at the same time.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Night Operations",
    "q": "To fly at night under Part 107 without a waiver, the aircraft must have anti-collision lighting visible for at least",
    "c": [
      "1 statute mile",
      "3 statute miles",
      "10 statute miles",
      "5 statute miles"
    ],
    "a": 1,
    "e": "Night operations require anti-collision lighting visible for at least 3 statute miles.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Night Operations",
    "q": "In addition to anti-collision lighting, night operations under Part 107 require the remote PIC to have",
    "c": [
      "a night-operations waiver",
      "filed a NOTAM",
      "a second-class medical certificate",
      "completed training that covers night operations"
    ],
    "a": 3,
    "e": "The remote PIC must complete initial or recurrent training that covers night operations.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Over Vehicles",
    "q": "Sustained flight of an sUAS over a person inside a moving vehicle is allowed only when",
    "c": [
      "the operation meets an over-people category or the occupants are participating",
      "the operation takes place in Class G airspace below 400 feet above the ground",
      "the remote pilot has notified the occupants and they have verbally given consent",
      "the flight is conducted during daylight and the vehicle is traveling under 25 mph"
    ],
    "a": 0,
    "e": "Flight over moving vehicles requires meeting an over-people category or that the occupants are participating in the operation.",
    "acs": "UA.I.E"
  },
  {
    "b": "Operations",
    "s": "Preflight",
    "q": "Before each flight, the remote PIC is required to",
    "c": [
      "obtain a standard weather briefing relayed verbally by the visual observer on site",
      "log the planned flight in IACRA and notify the nearest air traffic control facility",
      "assess the operating environment and ensure the aircraft is safe for operation",
      "file a flight plan with air traffic control and receive a clearance before launch"
    ],
    "a": 2,
    "e": "The remote PIC must assess the operating environment and ensure the sUAS is in a condition for safe operation.",
    "acs": "UA.V.F"
  },
  {
    "b": "Operations",
    "s": "CRM",
    "q": "Crew resource management (CRM) for sUAS operations refers to",
    "c": [
      "the process of coordinating directly with air traffic control",
      "the practice of managing the battery charge and discharge cycles",
      "the schedule for routine maintenance of the aircraft and batteries",
      "the effective use of all available resources, human and otherwise"
    ],
    "a": 3,
    "e": "CRM is the effective use of all available resources to conduct a safe operation.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "Responsibility",
    "q": "Who is directly responsible for, and the final authority over, an sUAS operation conducted under Part 107?",
    "c": [
      "The FAA",
      "The aircraft manufacturer",
      "The visual observer",
      "The remote pilot in command"
    ],
    "a": 3,
    "e": "The remote pilot in command is directly responsible for and the final authority over the operation.",
    "acs": "UA.I.B"
  },
  {
    "b": "Airspace",
    "s": "Altitude",
    "q": "The maximum altitude for a small unmanned aircraft under Part 107 is",
    "c": [
      "1,000 feet MSL when operating in uncontrolled airspace",
      "500 feet AGL as long as the aircraft stays in sight",
      "400 feet AGL, or within 400 feet of a structure",
      "200 feet AGL anywhere outside of controlled airspace"
    ],
    "a": 2,
    "e": "Maximum altitude is 400 feet AGL, or within 400 feet of a structure if operating higher.",
    "acs": "UA.I.B"
  },
  {
    "b": "Airspace",
    "s": "TFR",
    "q": "A temporary flight restriction (TFR) in the area where you plan to fly means that sUAS operations are",
    "c": [
      "allowed with a visual observer",
      "restricted or prohibited within the TFR",
      "unaffected",
      "allowed below 200 feet"
    ],
    "a": 1,
    "e": "A TFR restricts or prohibits flight, including sUAS operations, within the defined area.",
    "acs": "UA.II.A"
  },
  {
    "b": "Weather",
    "s": "Visibility",
    "q": "The minimum flight visibility for a Part 107 operation, as observed from the control station, is",
    "c": [
      "5 statute miles",
      "1 statute mile",
      "1 nautical mile",
      "3 statute miles"
    ],
    "a": 3,
    "e": "Minimum flight visibility is 3 statute miles from the control station.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Density Altitude",
    "q": "High density altitude (hot, high, and humid conditions) affects sUAS performance by",
    "c": [
      "having absolutely no effect at all on electric drones",
      "improving lift and thrust",
      "reducing performance because the air is less dense",
      "increasing maximum altitude"
    ],
    "a": 2,
    "e": "High density altitude reduces aircraft performance because the air is less dense.",
    "acs": "UA.III.B"
  },
  {
    "b": "Loading",
    "s": "Speed Limit",
    "q": "The maximum groundspeed allowed for a small unmanned aircraft under Part 107 is",
    "c": [
      "100 knots (115 mph)",
      "120 knots (138 mph)",
      "87 knots (100 mph)",
      "57 knots (65 mph)"
    ],
    "a": 2,
    "e": "Maximum groundspeed under Part 107 is 87 knots (100 mph).",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Weight",
    "q": "Adding payload weight to a small unmanned aircraft generally",
    "c": [
      "reduces flight time and maneuverability",
      "has no effect on performance",
      "increases maximum altitude",
      "increases flight time"
    ],
    "a": 0,
    "e": "Increased weight generally reduces endurance and maneuverability.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Regulations",
    "s": "Remote ID",
    "q": "Which part of 14 CFR establishes the Remote Identification requirements for unmanned aircraft?",
    "c": [
      "Part 89",
      "Part 91",
      "Part 61",
      "Part 47"
    ],
    "a": 0,
    "e": "14 CFR part 89 establishes the Remote Identification (Remote ID) requirements for unmanned aircraft.",
    "acs": "UA.I.F"
  },
  {
    "b": "Regulations",
    "s": "Over People",
    "q": "A Declaration of Compliance is",
    "c": [
      "an application a pilot files to request a waiver from a specific Part 107 operating rule",
      "a logbook entry in which the remote pilot records the date, duration, and location of each flight",
      "a registration receipt the FAA issues to the owner after the aircraft has been registered",
      "a manufacturer record submitted to the FAA certifying an sUAS meets Category 2 or 3 requirements"
    ],
    "a": 3,
    "e": "A Declaration of Compliance is a manufacturer record certifying the sUAS meets Category 2 or 3 over-people requirements.",
    "acs": "UA.I.E"
  },
  {
    "b": "Regulations",
    "s": "Over People",
    "q": "A Category 2 sUAS operated over people must not cause injury on impact exceeding",
    "c": [
      "11 ft-lb of kinetic energy",
      "25 ft-lb of kinetic energy",
      "55 ft-lb of kinetic energy",
      "there is no impact limit"
    ],
    "a": 0,
    "e": "Category 2 limits transferred impact energy to 11 ft-lb, with no lacerating parts, no safety defects, and a Declaration of Compliance.",
    "acs": "UA.I.E"
  },
  {
    "b": "Regulations",
    "s": "Over People",
    "q": "A Category 3 sUAS operated over people must not cause injury on impact exceeding",
    "c": [
      "there is no impact limit",
      "100 ft-lb of kinetic energy",
      "11 ft-lb of kinetic energy",
      "25 ft-lb of kinetic energy"
    ],
    "a": 3,
    "e": "Category 3 limits transferred impact energy to 25 ft-lb on impact.",
    "acs": "UA.I.E"
  },
  {
    "b": "Operations",
    "s": "Over People",
    "q": "Compared with Category 2, a Category 3 sUAS may NOT",
    "c": [
      "fly at night, even with the required anti-collision lighting",
      "be registered with the FAA under the usual process",
      "broadcast Remote ID using a standard onboard module",
      "operate over open-air assemblies of people"
    ],
    "a": 3,
    "e": "Category 3 operations may not be conducted over open-air assemblies of people.",
    "acs": "UA.I.E"
  },
  {
    "b": "Regulations",
    "s": "Over People",
    "q": "To qualify for Category 4 operations over people, a small unmanned aircraft must",
    "c": [
      "have an airworthiness certificate and be operated per its operating limitations",
      "be flown only at night while displaying anti-collision lighting visible for 3 statute miles",
      "weigh less than 0.55 lb so that it falls below the registration threshold entirely",
      "carry a deployable parachute system that has been tested and approved by an accredited laboratory"
    ],
    "a": 0,
    "e": "Category 4 requires an airworthiness certificate issued under part 21 and operation per the aircraft's operating limitations.",
    "acs": "UA.I.E"
  },
  {
    "b": "Operations",
    "s": "Over People",
    "q": "Operations over people may be conducted at night when",
    "c": [
      "never, because combining night flight with operations over people is always prohibited",
      "a single waiver covering night flight is held, regardless of the over-people category",
      "the aircraft weighs less than 0.55 lb and therefore poses very little risk to people below",
      "both the over-people category requirements and the night operation requirements are met"
    ],
    "a": 3,
    "e": "Over-people operations at night require meeting both the category requirements and the night requirements (anti-collision lighting plus training).",
    "acs": "UA.I.E"
  },
  {
    "b": "Regulations",
    "s": "Remote ID",
    "q": "The three ways to meet the Remote ID requirement are a standard Remote ID drone, a broadcast module, or",
    "c": [
      "filing a flight plan with the FAA before each individual flight",
      "operating within an FAA-Recognized Identification Area (FRIA)",
      "holding a Category 4 airworthiness certificate for the aircraft",
      "carrying a working transponder that reports to air traffic control"
    ],
    "a": 1,
    "e": "Remote ID is met with a standard Remote ID drone, a broadcast module, or by operating within a FRIA.",
    "acs": "UA.I.F"
  },
  {
    "b": "Operations",
    "s": "Remote ID",
    "q": "When using a Remote ID broadcast module, the remote pilot must",
    "c": [
      "use two completely separate control stations always",
      "fly only in Class G airspace",
      "stay below 100 feet",
      "keep the aircraft within visual line of sight"
    ],
    "a": 3,
    "e": "A Remote ID broadcast module requires the operation to remain within visual line of sight.",
    "acs": "UA.I.F"
  },
  {
    "b": "Regulations",
    "s": "Remote ID",
    "q": "In addition to its identity, location, altitude, velocity, and a time mark, a standard Remote ID drone broadcasts",
    "c": [
      "the control station location and an emergency status indication",
      "the battery temperature and the remaining charge of each onboard cell",
      "the destination airport identifier entered into the flight plan",
      "the remote pilot's certificate number and the date it was issued"
    ],
    "a": 0,
    "e": "Standard Remote ID also broadcasts the control station location and an emergency status indication.",
    "acs": "UA.I.F"
  },
  {
    "b": "Operations",
    "s": "FRIA",
    "q": "Within an FAA-Recognized Identification Area (FRIA), a drone that does not broadcast Remote ID may be flown only if it",
    "c": [
      "is under 0.25 lb and therefore exempt from the registration rules",
      "remains within visual line of sight of the operator",
      "stays below 50 feet above the ground for the entire flight",
      "carries a working transponder that reports its position to ATC"
    ],
    "a": 1,
    "e": "Inside a FRIA, a non-broadcasting drone must remain within visual line of sight of the operator.",
    "acs": "UA.I.F"
  },
  {
    "b": "Operations",
    "s": "Night Operations",
    "q": "The remote PIC may reduce the intensity of the required anti-collision lighting when",
    "c": [
      "it is in the interest of safety to do so",
      "a visual observer is present",
      "flying in Class G airspace",
      "the battery is low"
    ],
    "a": 0,
    "e": "The remote PIC may dim anti-collision lighting if a bright light would impair safe operation, using discretion in the interest of safety.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Airspace authorization",
    "q": "A UAS Facility Map shows a 100-foot ceiling for your area, but a structural inspection requires 150 feet. You should",
    "c": [
      "reduce the inspection to 100 feet and accept that you can never request anything more",
      "request further authorization, because LAANC will not approve above the charted ceiling",
      "ignore the facility map entirely, since it does not apply in uncontrolled Class G airspace at all",
      "fly at 150 feet under a standard LAANC approval, which always covers inspection work"
    ],
    "a": 1,
    "e": "Above the UAS Facility Map ceiling, you must seek further authorization rather than rely on standard LAANC approval.",
    "acs": "UA.II.B"
  },
  {
    "b": "Regulations",
    "s": "Over People",
    "q": "An sUAS that meets the requirements of more than one operations-over-people category",
    "c": [
      "must pick one category permanently",
      "may be operated under any category for which it qualifies",
      "is prohibited from flying over people",
      "must be separately re-registered for each and every category"
    ],
    "a": 1,
    "e": "A multi-category sUAS may be operated under any over-people category for which it qualifies.",
    "acs": "UA.I.E"
  },
  {
    "b": "Operations",
    "s": "Over People",
    "q": "A Category 3 sUAS may operate over people only when",
    "c": [
      "anywhere over moving people if the operation is conducted only during daylight hours",
      "over an open-air assembly of people as long as the aircraft stays below 100 feet and within visual line of sight",
      "over a closed or restricted-access site where those present are on notice, or not sustained over any person",
      "over any gathering once the manufacturer has issued a Declaration of Compliance"
    ],
    "a": 2,
    "e": "Category 3 may fly over people only within a closed or restricted-access site with notice, or without sustained flight over any person.",
    "acs": "UA.I.E"
  },
  {
    "b": "Operations",
    "s": "Lost Link",
    "q": "Knowing a small unmanned aircraft's programmed lost-link behavior before flight is important because it lets the remote PIC",
    "c": [
      "fly beyond visual line of sight as long as the link is automatic",
      "anticipate how the aircraft will act if the control link is lost",
      "skip the preflight check since the aircraft will recover on its own",
      "climb above 400 feet AGL to regain the lost control signal faster"
    ],
    "a": 1,
    "e": "Knowing the lost-link behavior lets the pilot anticipate the aircraft's response if the control link drops.",
    "acs": "UA.V.C"
  },
  {
    "b": "Operations",
    "s": "Interference",
    "q": "Operating a small unmanned aircraft close to metal structures or high-voltage power lines can",
    "c": [
      "have no measurable effect on the aircraft's control link or navigation systems",
      "increase battery life because the surrounding metal shields the aircraft from wind",
      "cause magnetic or radio interference that degrades control or navigation",
      "improve GPS accuracy by giving the receiver more fixed reference points nearby"
    ],
    "a": 2,
    "e": "Metal structures and power lines can cause magnetic or radio interference that degrades control or GPS navigation.",
    "acs": "UA.II.B"
  },
  {
    "b": "Operations",
    "s": "Preflight",
    "q": "A thorough preflight check for a Part 107 operation should include",
    "c": [
      "the aircraft and control link, power, and a survey of the operating area for hazards",
      "a current medical examination of the remote pilot completed within the last 24 months",
      "filing a flight plan with air traffic control and receiving a clearance before launch",
      "only the battery level, since the aircraft's software handles all other safety checks"
    ],
    "a": 0,
    "e": "Preflight includes the aircraft and control link, power, and a survey of the operating area for hazards.",
    "acs": "UA.V.F"
  },
  {
    "b": "Operations",
    "s": "Maintenance",
    "q": "When a manufacturer provides scheduled maintenance instructions for an sUAS, the operator should",
    "c": [
      "disregard them once the manufacturer's warranty period has fully expired",
      "perform maintenance only after the aircraft has been involved in a crash or hard landing event",
      "follow them, and otherwise maintain the aircraft so it stays in a condition for safe operation",
      "send the aircraft to an FAA facility for a scheduled annual inspection each year"
    ],
    "a": 2,
    "e": "Follow the manufacturer's maintenance schedule; absent one, maintain the aircraft so it remains in a condition for safe operation.",
    "acs": "UA.V.F"
  },
  {
    "b": "Operations",
    "s": "Human factors",
    "q": "Fatigue, dehydration, and stress affect a remote pilot by",
    "c": [
      "only mattering at night",
      "degrading performance and decision making",
      "improving reaction time",
      "having no effect on a ground-based pilot"
    ],
    "a": 1,
    "e": "Fatigue, dehydration, and stress degrade a pilot's performance and decision making, even on the ground.",
    "acs": "UA.V.E"
  },
  {
    "b": "Operations",
    "s": "IMSAFE",
    "q": "The IMSAFE checklist is used by a pilot to assess",
    "c": [
      "personal fitness for flight: illness, medication, stress, alcohol, fatigue, and emotion",
      "the aircraft's airworthiness, including the propellers, battery, and control link before flight",
      "current and forecast weather, including wind, visibility, and cloud ceilings at the site",
      "the class of airspace and any authorization needed before launching the operation"
    ],
    "a": 0,
    "e": "IMSAFE is a self-assessment of illness, medication, stress, alcohol, fatigue, and emotion.",
    "acs": "UA.V.E"
  },
  {
    "b": "Operations",
    "s": "Situational awareness",
    "q": "Near a non-towered airport, monitoring the common traffic advisory frequency (CTAF) helps a remote pilot",
    "c": [
      "stay aware of nearby manned aircraft operations",
      "extend flight time",
      "register the drone",
      "automatically obtain a full airspace authorization"
    ],
    "a": 0,
    "e": "Monitoring the CTAF builds awareness of nearby manned traffic at a non-towered airport.",
    "acs": "UA.V.D"
  },
  {
    "b": "Operations",
    "s": "See and Avoid",
    "q": "To meet see-and-avoid responsibilities, the remote PIC must",
    "c": [
      "operate only above 400 feet so that manned aircraft remain well below the drone",
      "maintain awareness and yield the right of way to all other aircraft",
      "equip the aircraft with a transponder and squawk the assigned discrete code",
      "rely solely on the aircraft's Remote ID broadcast to detect and avoid other traffic"
    ],
    "a": 1,
    "e": "The remote PIC must maintain awareness and yield the right of way to all other aircraft.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Crew Briefing",
    "q": "Before a crewed operation, briefing the visual observer and any crew on roles and emergency procedures primarily supports",
    "c": [
      "registration of the aircraft with the FAA before flight",
      "weather forecasting for the planned operating area",
      "Remote ID compliance for the aircraft during the flight",
      "crew resource management and safe coordination"
    ],
    "a": 3,
    "e": "A pre-operation crew briefing supports crew resource management and safe coordination.",
    "acs": "UA.V.D"
  },
  {
    "b": "Airspace",
    "s": "Prohibited Area",
    "q": "Operations within a prohibited area are",
    "c": [
      "allowed below 100 feet",
      "not allowed",
      "allowed with a waiver",
      "allowed with a visual observer"
    ],
    "a": 1,
    "e": "Flight within a prohibited area is not allowed.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "MOA",
    "q": "When operating near or under a Military Operations Area (MOA), a remote pilot should",
    "c": [
      "assume it is always inactive since most training happens at high altitude",
      "exercise caution because military training activity may be present",
      "request a specific waiver from the FAA before flying anywhere nearby",
      "climb above 400 feet to stay clear of any low-level military traffic"
    ],
    "a": 1,
    "e": "Use caution near a MOA, where military training activity may be present.",
    "acs": "UA.II.A"
  },
  {
    "b": "Airspace",
    "s": "NOTAM",
    "q": "A NOTAM (Notice to Air Missions) provides",
    "c": [
      "the maintenance history and current airworthiness status of an individual registered aircraft",
      "a permanent record of long-term airspace redesigns printed on each new sectional chart",
      "a detailed aviation weather forecast covering wind, visibility, and cloud layers for the next 24 hours",
      "time-critical aeronautical information not known far enough in advance to publicize otherwise"
    ],
    "a": 3,
    "e": "A NOTAM gives time-critical aeronautical information not known far enough in advance to publicize by other means.",
    "acs": "UA.II.B"
  },
  {
    "b": "Airspace",
    "s": "TFR",
    "q": "Before flying, a remote pilot can learn about temporary flight restrictions (TFRs) by",
    "c": [
      "checking NOTAMs and FAA sources",
      "reading the aircraft manual",
      "asking a visual observer",
      "calling the aircraft manufacturer"
    ],
    "a": 0,
    "e": "TFRs are published as NOTAMs and available through FAA sources, which should be checked before flight.",
    "acs": "UA.II.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "In a METAR, the code 'BKN' reports a sky condition of",
    "c": [
      "clear skies reported when no clouds are detected at all",
      "a few clouds covering 1/8 to 2/8 of the sky overhead",
      "broken clouds covering 5/8 to 7/8 of the sky",
      "overcast skies with cloud cover at a full 8/8 of the sky"
    ],
    "a": 2,
    "e": "BKN means broken clouds covering 5/8 to 7/8 of the sky.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "In a METAR, '24015G25KT' means the wind is",
    "c": [
      "from 240 degrees at 15 knots gusting to 25 knots",
      "from 150 degrees at a steady 24 knots",
      "calm at the surface with gusts to 24 knots",
      "variable in direction at a steady speed of 25 knots"
    ],
    "a": 0,
    "e": "24015G25KT means wind from 240 degrees at 15 knots, gusting to 25 knots.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "Stability",
    "q": "Unstable air is generally associated with",
    "c": [
      "stratiform clouds, steady widespread rain, smooth air, and gradually reducing visibility",
      "cumuliform clouds, turbulence, showery precipitation, and good visibility",
      "persistent fog, low stratus, and very poor visibility with little vertical motion",
      "clear skies with no cloud development and consistently calm surface winds all day"
    ],
    "a": 1,
    "e": "Unstable air brings cumuliform clouds, turbulence, showery precipitation, and generally good visibility.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Moisture",
    "q": "A small temperature-dewpoint spread indicates",
    "c": [
      "dry air with only high clouds above",
      "high humidity with possible fog or low clouds",
      "strong and gusty winds across the area",
      "a very high density altitude near the surface today"
    ],
    "a": 1,
    "e": "A small temperature-dewpoint spread signals high humidity and possible fog or low ceilings.",
    "acs": "UA.III.B"
  },
  {
    "b": "Regulations",
    "s": "Waivers",
    "q": "Which operation could be authorized by a Part 107 waiver?",
    "c": [
      "Careless or reckless operation",
      "Flight beyond visual line of sight",
      "Operating an aircraft over 55 pounds under Part 107",
      "Falsifying records"
    ],
    "a": 1,
    "e": "A Part 107 waiver can authorize deviations such as beyond-visual-line-of-sight flight when safety is shown.",
    "acs": "UA.I.D"
  },
  {
    "b": "Regulations",
    "s": "Certificate",
    "q": "While exercising the privileges of the certificate, the remote pilot must keep the remote pilot certificate",
    "c": [
      "on file with the FAA only, not on the operator",
      "in physical possession or immediately accessible",
      "at home in a safe place for secure long-term storage",
      "posted in a visible spot at the launch site"
    ],
    "a": 1,
    "e": "The remote pilot certificate must be in the pilot's physical possession or immediately accessible during operations.",
    "acs": "UA.I.C"
  },
  {
    "b": "Loading",
    "s": "Maximum Weight",
    "q": "To be operated under Part 107, a small unmanned aircraft must weigh, including everything on board or attached, less than",
    "c": [
      "25 pounds",
      "75 pounds",
      "55 pounds",
      "100 pounds"
    ],
    "a": 2,
    "e": "A small unmanned aircraft must weigh less than 55 pounds on takeoff, including everything on board or attached.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Performance",
    "q": "Adding weight to a multirotor drone generally requires the aircraft to",
    "c": [
      "climb to a higher maximum altitude before the motors reach their limit",
      "fly noticeably faster since the heavier airframe cuts through wind better",
      "use less battery current because the extra mass adds momentum in flight",
      "draw more power, reducing endurance and climb performance"
    ],
    "a": 3,
    "e": "More weight requires more power, which reduces endurance and climb performance.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Battery",
    "q": "Operating in cold temperatures typically affects a drone's battery by",
    "c": [
      "increasing its capacity",
      "eliminating the need to charge",
      "having no effect",
      "reducing its usable capacity and flight time"
    ],
    "a": 3,
    "e": "Cold temperatures reduce a battery's usable capacity, shortening flight time.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Structural",
    "q": "Abrupt, aggressive maneuvers increase the load on the airframe and can",
    "c": [
      "increase visibility",
      "reduce weight",
      "improve battery life",
      "overstress or damage the structure"
    ],
    "a": 3,
    "e": "Aggressive maneuvers raise the structural load and can overstress or damage the airframe.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Propellers",
    "q": "A nicked or cracked propeller should be",
    "c": [
      "kept in service until it visibly fails, since minor surface damage rarely affects performance",
      "taped over and reused for the rest of the flying season to avoid the replacement cost",
      "replaced before flight, because it degrades performance and can cause vibration or failure",
      "ignored as long as the drone still hovers and responds normally to the control inputs"
    ],
    "a": 2,
    "e": "A damaged propeller degrades performance and can cause vibration or failure, so it must be replaced before flight.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Wind",
    "q": "Flying into a strong headwind increases power demand and",
    "c": [
      "has no effect on battery",
      "increases groundspeed",
      "increases range",
      "reduces effective range and endurance"
    ],
    "a": 3,
    "e": "Flying into a strong headwind raises power demand, reducing effective range and endurance.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Preflight power",
    "q": "Before flight, the remote PIC should confirm the battery has enough charge for",
    "c": [
      "the first minute of flight only",
      "the manufacturer's warranty period",
      "exactly the hover time",
      "the planned operation plus a safe reserve"
    ],
    "a": 3,
    "e": "Confirm the battery has enough charge for the planned operation plus a safe reserve.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Temperature",
    "q": "As air temperature rises, air density decreases, which",
    "c": [
      "has no real measurable effect at all on rotorcraft",
      "reduces lift and thrust, degrading performance",
      "increases payload capacity",
      "improves lift and thrust"
    ],
    "a": 1,
    "e": "Higher temperatures lower air density, reducing lift and thrust and degrading performance.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Exceeding limits",
    "q": "Loading a drone beyond its maximum gross weight can result in",
    "c": [
      "a faster rate of climb, as the motors automatically compensate for the extra load",
      "improved stability in wind, since a heavier aircraft resists gusts more effectively",
      "longer flight time, because the added mass helps the aircraft glide more efficiently",
      "reduced climb, poor controllability, and inability to maintain altitude"
    ],
    "a": 3,
    "e": "Exceeding maximum gross weight reduces climb and controllability and can prevent maintaining altitude.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Loading",
    "s": "Planning",
    "q": "Considering weight and balance before adding a camera or payload helps ensure",
    "c": [
      "a faster GPS lock when the aircraft is first powered on before launch",
      "a lower aircraft registration fee because of the reduced takeoff weight",
      "the aircraft stays within its weight and center-of-gravity limits",
      "a longer manufacturer warranty on the airframe and the camera mount"
    ],
    "a": 2,
    "e": "Checking weight and balance keeps the aircraft within its weight and center-of-gravity limits.",
    "acs": "UA.IV.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "In a METAR, 'SCT' reports a sky condition of",
    "c": [
      "a broken cloud layer, 5/8 to 7/8 coverage",
      "scattered clouds, 3/8 to 4/8 coverage",
      "clear",
      "overcast"
    ],
    "a": 1,
    "e": "SCT means scattered clouds covering 3/8 to 4/8 of the sky.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "In a METAR, 'OVC' reports a sky condition of",
    "c": [
      "scattered clouds",
      "overcast, 8/8 coverage",
      "clear skies",
      "few clouds"
    ],
    "a": 1,
    "e": "OVC means overcast, with 8/8 sky coverage.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "In a METAR, 'FEW' reports a sky condition of",
    "c": [
      "few clouds, 1/8 to 2/8 coverage",
      "overcast",
      "broken",
      "scattered, 3/8 to 4/8"
    ],
    "a": 0,
    "e": "FEW means few clouds covering 1/8 to 2/8 of the sky.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "METAR",
    "q": "Visibility in a U.S. METAR is reported in",
    "c": [
      "nautical miles",
      "statute miles",
      "feet",
      "kilometers"
    ],
    "a": 1,
    "e": "U.S. METAR visibility is reported in statute miles.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "Forecasts",
    "q": "A TAF is a",
    "c": [
      "Total Airspace Figure printed on the sectional",
      "Temporary Altitude Filing made before takeoff",
      "Terminal Aerodrome Forecast for an airport area",
      "Turbulence Advisory Flag shown on weather charts"
    ],
    "a": 2,
    "e": "A TAF is a Terminal Aerodrome Forecast covering the area around an airport.",
    "acs": "UA.III.A"
  },
  {
    "b": "Weather",
    "s": "Fog",
    "q": "Radiation fog most commonly forms",
    "c": [
      "on clear, calm nights with high humidity as the ground cools",
      "over the open ocean where warm air moves across a cooler water surface",
      "during thunderstorms as heavy rain saturates the air near the surface",
      "on windy afternoons when rising thermals carry moisture quickly aloft"
    ],
    "a": 0,
    "e": "Radiation fog forms on clear, calm nights with high humidity as the ground cools.",
    "acs": "UA.III.B"
  },
  {
    "b": "Weather",
    "s": "Thunderstorms",
    "q": "When thunderstorms are present, a remote pilot should",
    "c": [
      "fly closer to inspect the storm and capture footage of the cloud base",
      "fly only below 100 feet, where the storm's strong winds cannot reach",
      "expect calm, smooth air in the area immediately around the storm cell",
      "avoid operating, due to turbulence, wind shear, and downbursts"
    ],
    "a": 3,
    "e": "Avoid operating near thunderstorms, which produce turbulence, wind shear, and downbursts.",
    "acs": "UA.III.B"
  },
  {
    "b": "Operations",
    "s": "Emergency",
    "q": "After deviating from a rule to handle an in-flight emergency, the remote PIC must, upon FAA request,",
    "c": [
      "submit a written report of the deviation",
      "pay a fine",
      "retake the entire proctored knowledge test",
      "surrender the certificate"
    ],
    "a": 0,
    "e": "Upon FAA request, the remote PIC must submit a written report describing the emergency deviation.",
    "acs": "UA.V.C"
  },
  {
    "b": "Operations",
    "s": "Airport operations",
    "q": "Operating a small unmanned aircraft in the vicinity of an airport requires the remote pilot to",
    "c": [
      "remain above 400 feet above the ground at all times while near the airport",
      "always obtain a written waiver from the FAA before operating near any airport",
      "monitor only the airport weather and disregard the other traffic in the pattern",
      "not interfere with operations at the airport and give way to manned aircraft"
    ],
    "a": 3,
    "e": "Near an airport, the operation must not interfere with airport operations and must give way to manned aircraft.",
    "acs": "UA.V.B"
  },
  {
    "b": "Operations",
    "s": "Carriage of Property",
    "q": "Carrying property for compensation under Part 107 is allowed only if",
    "c": [
      "the total weight stays under 55 lb, no hazardous material is carried, and the operation is within one state",
      "the delivery is flown at night under a waiver, with anti-collision lighting and the payload fully sealed for transport",
      "the flight crosses state lines so that it qualifies as interstate commerce under federal rules",
      "the aircraft weighs more than 55 lb and the operator holds an exemption issued under part 91"
    ],
    "a": 0,
    "e": "Carrying property for compensation requires total weight under 55 lb, no hazardous materials, and operation within a single state.",
    "acs": "UA.I.B"
  },
  {
    "b": "Operations",
    "s": "Visual Observer",
    "q": "A visual observer used to satisfy see-and-avoid must",
    "c": [
      "be able to see the aircraft and communicate its position to the remote PIC",
      "take over the flight controls whenever the remote pilot loses sight",
      "hold a current remote pilot certificate issued under Part 107 rules",
      "remain seated inside a vehicle that is parked near the launch and recovery area"
    ],
    "a": 0,
    "e": "A visual observer must be able to see the aircraft and communicate its position and any hazards to the remote PIC.",
    "acs": "UA.I.B"
  },
  {
    "b": "Charts",
    "s": "Airspace Symbols",
    "fig": "sectional_poc_1",
    "q": "In the figure, the dashed blue ring around the airport at marker 1 depicts which class of airspace?",
    "c": [
      "Class D airspace, around a field with a control tower",
      "Class B airspace, surrounding a major airport",
      "Class E surface area, at a field with no tower",
      "Class C airspace, served by a tower and approach control"
    ],
    "a": 0,
    "e": "A dashed blue line marks Class D airspace, usually a small ring around an airport that has an operating control tower.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airport Symbols",
    "fig": "sectional_poc_1",
    "q": "On the figure, the airport at marker 2 is drawn in magenta. That color tells you it:",
    "c": [
      "has no operating control tower",
      "is a private field that is not open to the public",
      "sits within Class B airspace",
      "is closed to all small unmanned aircraft"
    ],
    "a": 0,
    "e": "Magenta airport symbols are non-towered; blue symbols mark fields with an operating control tower.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Obstacles",
    "fig": "sectional_poc_1",
    "q": "The obstacle at marker 3 is labeled 1549 (549). Its top is at:",
    "c": [
      "1,000 feet, taken as the difference of the two numbers",
      "1,549 feet MSL, which is 549 feet above the ground",
      "549 feet MSL, with the top reaching 1,549 feet AGL",
      "1,549 feet above the ground at the obstacle base"
    ],
    "a": 1,
    "e": "An obstacle's two numbers are the top height in feet MSL and, in parentheses, the height in feet above ground level.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Terrain",
    "fig": "sectional_poc_1",
    "q": "The large 2 and small 5 printed in the upper-right quadrant of the figure are a maximum elevation figure. They mean the highest terrain or obstacle in that quadrant is:",
    "c": [
      "25,000 feet MSL",
      "2,500 feet above ground level",
      "250 feet, read as a per-mile gradient",
      "2,500 feet MSL"
    ],
    "a": 3,
    "e": "A maximum elevation figure gives the highest terrain or obstacle in that quadrant in thousands and hundreds of feet MSL, so a large 2 and small 5 mean 2,500 feet.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Airspace Symbols",
    "fig": "sectional_class_c",
    "q": "In the figure, the two solid magenta circles around the airport at marker 1 depict which class of airspace?",
    "c": [
      "Class E to the surface, shown as a dashed magenta ring",
      "Class C, shown as solid magenta rings",
      "Class B, shown as solid blue rings",
      "Class D, shown as a dashed blue ring"
    ],
    "a": 1,
    "e": "Class C airspace is drawn with solid magenta lines, usually an inner surface core and an outer shelf.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Symbols",
    "fig": "sectional_class_c",
    "q": "The dashed magenta ring around the airport at marker 2 indicates:",
    "c": [
      "the lateral limits of a military operations area",
      "Class C airspace around a towered field",
      "Class E airspace that starts at the surface",
      "a restricted area with a controlling agency"
    ],
    "a": 2,
    "e": "A dashed magenta line marks Class E airspace that begins at the surface, often around a non-towered field with an instrument approach.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airport Symbols",
    "fig": "sectional_class_c",
    "q": "The airport inside the Class C airspace at marker 1 is drawn in blue, which tells you it:",
    "c": [
      "has no weather reporting available",
      "lies beneath a shelf of Class B airspace",
      "is limited to operations during daylight only",
      "has an operating control tower"
    ],
    "a": 3,
    "e": "Blue airport symbols mark fields with an operating control tower; Class C airports are always towered.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Airspace Notation",
    "fig": "sectional_ceilfloor",
    "q": "On the figure, the airspace at marker 1 is labeled 55 over 12. Its ceiling and floor are:",
    "c": [
      "a ceiling of 12,000 ft over a floor of 5,500 ft",
      "5,500 ft MSL ceiling and 1,200 ft MSL floor",
      "5,500 ft AGL ceiling and 1,200 ft AGL floor",
      "55,000 ft and 12,000 ft, read in tens of thousands"
    ],
    "a": 1,
    "e": "Stacked airspace numbers are hundreds of feet MSL: the top is the ceiling and the bottom the floor, so 55 over 12 is 5,500 over 1,200.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Notation",
    "fig": "sectional_ceilfloor",
    "q": "In the 100 over SFC label at marker 2, SFC means the airspace:",
    "c": [
      "extends down to the surface",
      "has a floor at 100 ft above ground",
      "is a special flight rules corridor",
      "is closed below 10,000 ft MSL"
    ],
    "a": 0,
    "e": "SFC means surface; the airspace reaches from the ground up to the ceiling shown above it.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Notation",
    "fig": "sectional_ceilfloor",
    "q": "The faded magenta line at marker 3, with no floor figure printed, tells you Class E airspace there begins at:",
    "c": [
      "18,000 ft MSL",
      "1,200 ft AGL",
      "the surface",
      "700 ft AGL"
    ],
    "a": 3,
    "e": "A faded magenta line with no floor figure marks Class E starting at 700 ft AGL; a printed magenta number would show a different (higher) floor in MSL.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Special Use",
    "fig": "sectional_sua",
    "q": "The blue hatched boundary labeled R-2501 at marker 1 on the figure is:",
    "c": [
      "a military operations area, or MOA",
      "a restricted area",
      "a temporary flight restriction zone",
      "the lateral edge of Class B airspace"
    ],
    "a": 1,
    "e": "A blue hatched boundary marks special use airspace such as a prohibited or restricted area; the R prefix means restricted.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Special Use",
    "fig": "sectional_sua",
    "q": "Operating inside the restricted area at marker 1 while it is active generally requires:",
    "c": [
      "staying below 400 ft above ground level",
      "permission from the controlling agency",
      "only a current weather briefing on file",
      "no action, since Part 107 is always exempt"
    ],
    "a": 1,
    "e": "Restricted areas can be hazardous when active; entering one generally requires permission from the using or controlling agency.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Visual Checkpoint",
    "fig": "sectional_sua",
    "q": "The magenta flag symbol at marker 2 on the figure marks:",
    "c": [
      "an airport offering fuel and services",
      "a VFR visual checkpoint",
      "a parachute jumping area",
      "a seaplane base on the water"
    ],
    "a": 1,
    "e": "A flag symbol marks a VFR visual checkpoint, a prominent landmark used to report position or aid navigation.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Symbols",
    "fig": "sectional_class_b",
    "q": "The concentric solid blue circles around the airport at marker 1 depict which class of airspace?",
    "c": [
      "a restricted area marked by a blue hatched line",
      "Class B, shown as solid blue rings",
      "Class C, shown as solid magenta rings",
      "Class D, shown as a dashed blue ring"
    ],
    "a": 1,
    "e": "Class B airspace is drawn with solid blue lines, often several rings shaped like an upside-down wedding cake.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Notation",
    "fig": "sectional_class_b",
    "q": "The 100 over 30 label at marker 2 gives that Class B shelf's ceiling and floor as:",
    "c": [
      "1,000 ft and 300 ft, read in hundreds of feet",
      "10,000 ft MSL ceiling and 3,000 ft MSL floor",
      "10,000 ft AGL ceiling and 3,000 ft AGL floor",
      "a floor of 10,000 ft below a 3,000 ft ceiling"
    ],
    "a": 1,
    "e": "Stacked numbers are hundreds of feet MSL, so 100 over 30 is a shelf from 3,000 up to 10,000 ft MSL.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Compliance",
    "fig": "sectional_class_b",
    "q": "To fly a small drone inside the Class B airspace at marker 1, a Part 107 pilot must first:",
    "c": [
      "squawk a discrete transponder code",
      "file a flight plan with Flight Service",
      "get airspace authorization from ATC",
      "simply stay below 400 ft above ground"
    ],
    "a": 2,
    "e": "Operations in controlled airspace such as Class B require prior ATC authorization, usually through LAANC or DroneZone.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Special Use",
    "fig": "sectional_symbols",
    "q": "The grey line labeled VR1234 at marker 1 on the figure is:",
    "c": [
      "a military training route",
      "a published visual flight rules route",
      "a low-frequency airway for navigation",
      "the boundary of a restricted area"
    ],
    "a": 0,
    "e": "Lines labeled VR or IR with a number are military training routes, where high-speed military traffic may operate.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Special Use",
    "fig": "sectional_symbols",
    "q": "The parachute symbol at marker 2 marks an area where you should expect:",
    "c": [
      "seaplane traffic out on the water",
      "parachute jumping activity",
      "glider towing operations only",
      "frequent hot air balloon launches"
    ],
    "a": 1,
    "e": "A parachute symbol marks a parachute jumping area; expect jumpers and jump aircraft nearby.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airport Symbols",
    "fig": "sectional_symbols",
    "q": "The magenta anchor symbol at marker 3 indicates:",
    "c": [
      "a seaplane base",
      "a heliport for rotorcraft",
      "a private grass airstrip",
      "a parachute landing zone"
    ],
    "a": 0,
    "e": "An anchor symbol marks a seaplane base, an area used by aircraft that operate from water.",
    "acs": "UA.II.B"
  },
  {
    "b": "Charts",
    "s": "Airspace Symbols",
    "fig": "sectional_point_airspace",
    "q": "At marker 1, which lies inside the dashed blue ring around the airport, the airspace is:",
    "c": [
      "Class D, up to its charted ceiling",
      "Class G, uncontrolled airspace",
      "Class C, with a surface core and an outer shelf",
      "Class B, from the surface upward"
    ],
    "a": 0,
    "e": "A dashed blue ring marks Class D around a towered airport, from the surface up to the ceiling shown in the dashed box.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Symbols",
    "fig": "sectional_point_airspace",
    "q": "Marker 2 sits on the faded side of the magenta boundary. The airspace there is:",
    "c": [
      "a Class B surface area",
      "Class D around a towered airport",
      "Class E starting at 700 ft AGL",
      "a prohibited area you must avoid"
    ],
    "a": 2,
    "e": "The faded side of a magenta line is where Class E begins at 700 ft AGL.",
    "acs": "UA.II.A"
  },
  {
    "b": "Charts",
    "s": "Airspace Symbols",
    "fig": "sectional_point_airspace",
    "q": "Marker 3 is in open country with no ring or shading, so the surface airspace there is:",
    "c": [
      "Class E down to the surface",
      "Class G up to 1,200 ft AGL",
      "Class B up to 10,000 ft",
      "Class C beneath a shelf"
    ],
    "a": 1,
    "e": "Open areas with no ring or shading are Class G (uncontrolled) up to 1,200 ft AGL, with Class E above.",
    "acs": "UA.II.A"
  },
  {
    "s": "METAR",
    "acs": "UA.III.A",
    "q": "A METAR reads: KAPA 141953Z 30012KT 10SM FEW070 SCT250 24/09 A3005. The ceiling at this station is:",
    "c": [
      "an overcast at 25,000 ft",
      "a ceiling at 1,200 ft AGL",
      "a broken layer at 7,000 ft overhead",
      "no ceiling is reported"
    ],
    "a": 3,
    "e": "A ceiling is the lowest broken or overcast layer; with only FEW and SCT reported here, there is no ceiling.",
    "b": "Weather"
  },
  {
    "s": "METAR",
    "acs": "UA.III.A",
    "q": "In the METAR KDEN 121853Z 09018G28KT 10SM BKN035 OVC060 12/04 A2992, the wind and altimeter are:",
    "c": [
      "wind 090 at 28 knots steady, altimeter 29.92 inches",
      "wind 090 at 18 gusting 28 kt, altimeter 29.92",
      "wind 900 at 18 kt, altimeter 2,992 ft",
      "wind 090 at 18 kt, pressure 992 mb"
    ],
    "a": 1,
    "e": "09018G28KT is wind from 090 true at 18 knots gusting 28, and A2992 is an altimeter setting of 29.92 inches of mercury.",
    "b": "Weather"
  },
  {
    "s": "METAR",
    "acs": "UA.III.A",
    "q": "In a METAR, the present-weather code '-SHRA' indicates:",
    "c": [
      "light snow showers",
      "light rain showers",
      "heavy continuous rain",
      "freezing rain"
    ],
    "a": 1,
    "e": "The minus sign means light, SH means showers, and RA means rain, so -SHRA is light rain showers.",
    "b": "Weather"
  },
  {
    "s": "METAR",
    "acs": "UA.III.B",
    "q": "A METAR shows 15/14 with 1SM BR. The small temperature-dewpoint spread indicates:",
    "c": [
      "high density altitude conditions",
      "a strong low-level temperature inversion",
      "air near saturation (fog likely)",
      "unusually dry air aloft"
    ],
    "a": 2,
    "e": "When temperature and dewpoint are within a few degrees, the air is near saturation and fog or mist is likely.",
    "b": "Weather"
  },
  {
    "s": "METAR",
    "acs": "UA.III.A",
    "q": "A METAR ends with the group 'A3012'. This is:",
    "c": [
      "a pressure altitude reading of 3,012 ft",
      "an altimeter setting, 30.12 inHg",
      "a visibility of 3,012 meters",
      "a temperature of 30.12 degrees C"
    ],
    "a": 1,
    "e": "The A prefix reports the altimeter setting in inches of mercury, so A3012 is 30.12 inHg.",
    "b": "Weather"
  },
  {
    "s": "TAF",
    "acs": "UA.III.A",
    "q": "A TAF includes 'TEMPO 2022 5SM BR'. Between 2000Z and 2200Z you should expect:",
    "c": [
      "clearing to 5 SM by 2000Z",
      "a permanent change to visibility 5 SM",
      "brief periods of 5 SM in mist",
      "5 SM only after 2200Z"
    ],
    "a": 2,
    "e": "TEMPO marks temporary fluctuations expected to last less than an hour each within the stated window.",
    "b": "Weather"
  },
  {
    "s": "TAF",
    "acs": "UA.III.A",
    "q": "A TAF line 'FM1500 31015G25KT 3SM' tells you that from 1500Z:",
    "c": [
      "those conditions begin and persist from 1500Z",
      "a 30 percent chance applies after 1500Z",
      "those conditions may briefly appear near 1500Z",
      "those conditions ended at 1500Z"
    ],
    "a": 0,
    "e": "FM (from) marks a rapid, lasting change; the new conditions begin at that time and continue until the next change.",
    "b": "Weather"
  },
  {
    "s": "TAF",
    "acs": "UA.III.A",
    "q": "In a TAF, 'PROB40 2124 1SM TSRA' means during 2100 to 2400Z there is:",
    "c": [
      "a 40% chance of 1 SM in thunderstorm rain",
      "a 40% improvement in the visibility",
      "thunderstorms ending by 2100Z",
      "a guaranteed period of heavy thunderstorms"
    ],
    "a": 0,
    "e": "PROB40 states a 40 percent probability of the listed conditions, here 1 SM visibility in thunderstorms and rain.",
    "b": "Weather"
  },
  {
    "s": "Thunderstorms",
    "acs": "UA.III.B",
    "q": "The three stages of a thunderstorm's life cycle, in order, are:",
    "c": [
      "building, anvil, outflow",
      "mature, cumulus, dissipating",
      "forming, peak, collapse",
      "cumulus, mature, dissipating"
    ],
    "a": 3,
    "e": "A thunderstorm grows through the cumulus (updraft) stage, the mature (updraft and downdraft) stage, then the dissipating stage.",
    "b": "Weather"
  },
  {
    "s": "Thunderstorms",
    "acs": "UA.III.B",
    "q": "A thunderstorm is most hazardous during which stage, when updrafts and downdrafts coexist?",
    "c": [
      "the dissipating stage",
      "the anvil stage",
      "the cumulus stage",
      "the mature stage"
    ],
    "a": 3,
    "e": "The mature stage has the strongest turbulence, wind shear, hail, and lightning as updrafts and downdrafts occur together.",
    "b": "Weather"
  },
  {
    "s": "Thunderstorms",
    "acs": "UA.III.B",
    "q": "The sudden wind shift and gusty surface winds felt just before a thunderstorm arrives come from:",
    "c": [
      "a low-level temperature inversion lifting",
      "cold downdraft outflow ahead of the storm",
      "the anvil cloud blowing downwind",
      "warm updraft air feeding into the storm base"
    ],
    "a": 1,
    "e": "Cold downdraft air spreads out ahead of the storm as a gust front, causing an abrupt wind shift and strong gusts.",
    "b": "Weather"
  },
  {
    "s": "Hazards",
    "acs": "UA.III.B",
    "q": "Embedded thunderstorms are especially dangerous because they are:",
    "c": [
      "hidden inside other cloud layers",
      "weaker than isolated storms",
      "always accompanied by large damaging hail",
      "found only in mountainous terrain"
    ],
    "a": 0,
    "e": "Embedded thunderstorms are concealed within surrounding cloud layers, so they are hard to see and avoid.",
    "b": "Weather"
  },
  {
    "s": "Stability",
    "acs": "UA.III.B",
    "q": "Unstable air most often brings:",
    "c": [
      "smooth, stable flying conditions all day",
      "steady, widespread light drizzle and haze",
      "a strong low-level temperature inversion",
      "showery precipitation and good visibility"
    ],
    "a": 3,
    "e": "Unstable air produces cumuliform clouds, showery precipitation, good visibility, and turbulence.",
    "b": "Weather"
  },
  {
    "s": "Stability",
    "acs": "UA.III.B",
    "q": "A stable air mass most commonly brings:",
    "c": [
      "brief heavy showers",
      "towering cumulus buildups",
      "strong gusty winds and heavy turbulence",
      "poor visibility with haze or fog"
    ],
    "a": 3,
    "e": "Stable air resists vertical motion, giving stratiform clouds, steady precipitation, smooth air, and poor visibility.",
    "b": "Weather"
  },
  {
    "s": "Density Altitude",
    "acs": "UA.III.B",
    "q": "On a hot, humid afternoon at a high-elevation field, a multirotor will most likely:",
    "c": [
      "climb noticeably faster than a cool day",
      "gain endurance in the warm air",
      "make less lift and climb sluggishly",
      "hover with no performance change"
    ],
    "a": 2,
    "e": "Hot, high, and humid conditions raise density altitude, thinning the air so props make less lift and motors work harder.",
    "b": "Weather"
  },
  {
    "s": "Density Altitude",
    "acs": "UA.III.B",
    "q": "Which change would most increase density altitude on the flight line?",
    "c": [
      "a rise in temperature and humidity",
      "a rise in station pressure",
      "a fall in field elevation",
      "a sharp drop in outside temperature"
    ],
    "a": 0,
    "e": "Higher temperature, higher humidity, and higher elevation all raise density altitude and reduce performance.",
    "b": "Weather"
  },
  {
    "s": "Weather Sources",
    "acs": "UA.III.A",
    "q": "An automated station broadcasting continuous local weather to pilots is an:",
    "c": [
      "area forecast",
      "AWOS or ASOS",
      "winds aloft table",
      "AIRMET or SIGMET"
    ],
    "a": 1,
    "e": "AWOS and ASOS are automated surface observing systems that broadcast current local weather continuously.",
    "b": "Weather"
  },
  {
    "s": "Weather Sources",
    "acs": "UA.III.A",
    "q": "At a towered airport, ATIS provides:",
    "c": [
      "a 30-hour area forecast",
      "a recorded airport and weather loop",
      "regional NOTAMs only",
      "live two-way radio control from the tower"
    ],
    "a": 1,
    "e": "ATIS is a continuous recorded broadcast of current airport and weather information, updated as conditions change.",
    "b": "Weather"
  },
  {
    "s": "Weather Sources",
    "acs": "UA.III.A",
    "q": "The best official source for a full preflight weather briefing is:",
    "c": [
      "yesterday's forecast",
      "Flight Service or aviationweather.gov",
      "a friend at the field",
      "any consumer television weather channel"
    ],
    "a": 1,
    "e": "Flight Service (1-800-WX-BRIEF) and aviationweather.gov provide official aviation weather for preflight planning.",
    "b": "Weather"
  },
  {
    "s": "Pressure Systems",
    "acs": "UA.III.B",
    "q": "In the Northern Hemisphere, surface wind around a low-pressure area flows:",
    "c": [
      "counterclockwise and inward",
      "clockwise and spiraling outward",
      "outward in all directions",
      "straight toward the center"
    ],
    "a": 0,
    "e": "Around a Northern Hemisphere low, surface wind spirals counterclockwise and inward toward the center.",
    "b": "Weather"
  },
  {
    "s": "Pressure Systems",
    "acs": "UA.III.B",
    "q": "Surface wind is usually slower and angled toward low pressure compared with wind aloft, mainly because of:",
    "c": [
      "surface friction",
      "the jet stream overhead",
      "frontal lifting",
      "the Coriolis force alone"
    ],
    "a": 0,
    "e": "Friction near the ground slows the wind and shifts it toward lower pressure, an effect that fades with height.",
    "b": "Weather"
  },
  {
    "s": "Hazards",
    "acs": "UA.III.B",
    "q": "Frost forming overnight on a multirotor's arms and propellers can:",
    "c": [
      "improve grip on the propellers",
      "add helpful weight for stability",
      "have no effect on flight",
      "disrupt airflow and reduce lift"
    ],
    "a": 3,
    "e": "Frost roughens the surfaces and disrupts smooth airflow over the props, reducing lift much as it does on a wing.",
    "b": "Weather"
  },
  {
    "s": "Inversion",
    "acs": "UA.III.B",
    "q": "A ground-based temperature inversion at night often produces:",
    "c": [
      "towering cumulus clouds",
      "heavy showery precipitation",
      "strong turbulence through the whole layer",
      "smooth air below with wind shear on top"
    ],
    "a": 3,
    "e": "An inversion is very stable, giving smooth air and trapped haze below, but wind shear can occur at the top of the layer.",
    "b": "Weather"
  },
  {
    "s": "Clouds",
    "acs": "UA.III.B",
    "q": "With a surface temperature of 77F and a dewpoint of 59F, the convective cloud base is roughly:",
    "c": [
      "about 4,000 ft AGL",
      "right at the surface",
      "about 12,000 ft AGL",
      "about 500 ft AGL"
    ],
    "a": 0,
    "e": "The spread is about 18F; dividing by 4.4F per 1,000 ft puts the convective cloud base near 4,000 ft AGL.",
    "b": "Weather"
  },
  {
    "s": "Load Factor",
    "q": "As a multirotor flies a steeper, faster banked turn, the load on the motors and airframe:",
    "c": [
      "falls to zero",
      "increases",
      "stays exactly the same",
      "decreases"
    ],
    "a": 1,
    "e": "Steeper and faster maneuvers raise the load factor, so the motors and structure carry more load.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Load Factor",
    "q": "In a coordinated level turn, the load factor is greatest at which bank angle?",
    "c": [
      "30 degrees",
      "15 degrees",
      "60 degrees",
      "wings level"
    ],
    "a": 2,
    "e": "Load factor rises with bank angle; a 60-degree bank in level flight is about 2 Gs, far more than shallow turns.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Load Factor",
    "q": "Pulling out of a fast descent or snapping through a hard turn raises the load factor, which:",
    "c": [
      "demands more power and stresses the frame",
      "actually lowers the power the motors must produce",
      "has no effect on the motors",
      "cools the battery pack"
    ],
    "a": 0,
    "e": "A higher load factor means the aircraft effectively weighs more for that moment, needing more thrust and stressing the airframe.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Load Factor",
    "q": "Repeated aggressive, high-load maneuvers will tend to:",
    "c": [
      "have no real cost",
      "noticeably extend the total available flight time",
      "drain the battery faster and stress motors",
      "cool the motors down"
    ],
    "a": 2,
    "e": "High-load maneuvers pull more current and add mechanical stress, cutting flight time and wearing components.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Ground Effect",
    "q": "Hovering within about one rotor span of the ground, in ground effect, generally:",
    "c": [
      "requires far more power than a high hover",
      "is impossible to do safely",
      "eliminates all lift",
      "uses less power than a high hover"
    ],
    "a": 3,
    "e": "Close to the surface the rotors work more efficiently, so a hover in ground effect uses less power than one up high.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Ground Effect",
    "q": "As a multirotor climbs up out of ground effect, the pilot should expect it to:",
    "c": [
      "need more power to hold the climb",
      "suddenly gain extra free lift for the climb",
      "become noticeably lighter",
      "ignore the wind entirely"
    ],
    "a": 0,
    "e": "Leaving ground effect increases induced drag, so more power is needed to keep climbing.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Descent",
    "q": "Descending straight down too quickly, a multirotor can settle into its own downwash and:",
    "c": [
      "gain extra lift and climb faster",
      "recharge its own battery",
      "become far more stable",
      "lose lift and be hard to arrest"
    ],
    "a": 3,
    "e": "A rapid vertical descent into the rotors' own turbulent wake (settling with power) causes a loss of lift that is hard to stop.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Descent",
    "q": "The best way to break out of settling with power during a fast vertical descent is to:",
    "c": [
      "descend even faster to push through it",
      "add ballast payload",
      "move forward into undisturbed air",
      "simply hover in place"
    ],
    "a": 2,
    "e": "Moving forward or sideways carries the aircraft out of its descending column of disturbed air and restores lift.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Descent",
    "q": "To avoid settling with power, a multirotor should avoid:",
    "c": [
      "rapid straight-down descents",
      "any forward flight whatsoever",
      "hovering in ground effect",
      "climbing at all"
    ],
    "a": 0,
    "e": "Settling with power comes from fast vertical descents with little horizontal movement, so add forward speed when descending.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Descent",
    "q": "During an automated vertical descent to land, a sudden wobble and increased sink can mean the aircraft is:",
    "c": [
      "overheating the GPS receiver",
      "gaining extra free lift from the ground",
      "descending into its own rotor wash",
      "too light to land"
    ],
    "a": 2,
    "e": "A wobble and rapid sink on vertical descent can signal settling with power; nudging the aircraft laterally usually recovers it.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Weight and Balance",
    "q": "In weight and balance, the moment of a payload equals:",
    "c": [
      "its arm divided by its weight",
      "its weight minus the total empty aircraft weight",
      "battery voltage times its weight",
      "its weight times its arm from the reference"
    ],
    "a": 3,
    "e": "Moment is weight multiplied by the arm (distance) from the reference point; moments determine the center of gravity.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Center of Gravity",
    "q": "The center-of-gravity envelope published by the manufacturer defines:",
    "c": [
      "the legal registration weight",
      "the maximum permitted total flight time in minutes",
      "the allowable range for the balance point",
      "the radio frequency band"
    ],
    "a": 2,
    "e": "The CG envelope is the allowable range within which the balance point must stay for safe, controllable flight.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Weight Distribution",
    "q": "If the load is not centered, a multirotor holds its position by:",
    "c": [
      "shutting down the lower-side motors entirely",
      "tilting and running some motors harder",
      "spinning all motors faster",
      "ignoring the imbalance"
    ],
    "a": 1,
    "e": "An off-center load forces a constant tilt and makes some motors work harder, wasting power and adding wear.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Battery Reserve",
    "q": "A sound battery-reserve practice is to plan the flight so you land with:",
    "c": [
      "a reserve above the return-to-home level",
      "only enough for takeoff",
      "just barely enough to reach the landing zone",
      "zero percent remaining"
    ],
    "a": 0,
    "e": "Always keep a margin above the return-to-home or auto-land threshold to cover wind, distance, and voltage sag.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Endurance",
    "q": "A pack rated 100 Wh feeding motors that draw about 300 W in hover gives a rough hover time of:",
    "c": [
      "about 45 minutes",
      "about 2 hours",
      "about 20 minutes",
      "about 5 minutes"
    ],
    "a": 2,
    "e": "Roughly, 100 watt-hours divided by 300 watts is about a third of an hour, near 20 minutes before any reserve.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Thrust Margin",
    "q": "Carrying near-maximum payload leaves the motors with:",
    "c": [
      "far more reserve thrust than an empty aircraft",
      "an unlimited climb rate",
      "cooler motor temperatures",
      "little extra thrust for gusts or climbs"
    ],
    "a": 3,
    "e": "Near maximum weight the thrust margin is small, so gusts or a needed climb can outrun the motors' remaining power.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Wind",
    "q": "To track straight across the ground in a crosswind, a multirotor must:",
    "c": [
      "crab, angling into the wind",
      "point straight at the target only",
      "fly sideways downwind",
      "stop and hover"
    ],
    "a": 0,
    "e": "The aircraft must angle into the wind (crab) so its ground track stays straight despite the drift.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Wind",
    "q": "Turning downwind, a pilot may perceive the aircraft speeding up because:",
    "c": [
      "the electric motors suddenly produce more power",
      "groundspeed increases with the tailwind",
      "the air is thinner downwind",
      "the battery surges"
    ],
    "a": 1,
    "e": "A tailwind raises groundspeed, which can look like acceleration and lead to overshooting the intended point.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Wind",
    "q": "Planning an out-and-back flight in wind, it is usually smart to head out:",
    "c": [
      "downwind first so you reach it much sooner",
      "whichever way is closer",
      "upwind first, returning with a tailwind",
      "only when the wind is calm"
    ],
    "a": 2,
    "e": "Flying out into the wind means the return leg, flown on a lower battery, has a helpful tailwind.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Wind",
    "q": "When winds are strong, a pilot should add extra:",
    "c": [
      "battery reserve for higher power use",
      "extra payload weight to add stability",
      "speed beyond the limit",
      "altitude beyond 400 ft AGL"
    ],
    "a": 0,
    "e": "Wind raises power demand, especially into a headwind, so plan a larger battery reserve.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Propellers",
    "q": "Compared with the stock propellers, larger or higher-pitch propellers generally:",
    "c": [
      "are always a completely safe upgrade",
      "reduce the aircraft weight",
      "change thrust and current draw",
      "have no effect on the motors"
    ],
    "a": 2,
    "e": "Non-stock propellers change the load on the motors and speed controllers and can alter flight time, so follow the maker's specs.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Performance",
    "q": "Warmer, less dense air on a hot day means a multirotor's propellers produce:",
    "c": [
      "noticeably more thrust for the same speed",
      "less thrust for the same motor speed",
      "zero thrust at all",
      "the same thrust as a cold day"
    ],
    "a": 1,
    "e": "Less dense air gives each propeller less to push against, so thrust drops for a given motor speed, hurting performance.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Performance",
    "q": "Adding payload up to the aircraft's limit will reduce its:",
    "c": [
      "radio range",
      "propeller count",
      "climb rate and thrust margin",
      "maximum total takeoff weight rating"
    ],
    "a": 2,
    "e": "More weight leaves less spare thrust, cutting climb rate and the margin available for maneuvers and gusts.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Gusts",
    "q": "Flying near maximum weight in gusty wind is risky because a gust can:",
    "c": [
      "demand thrust the motors cannot spare",
      "improve overall stability",
      "momentarily make the whole drone lighter",
      "recharge the battery pack"
    ],
    "a": 0,
    "e": "At near-maximum weight the motors have little spare thrust, so a strong gust can exceed what they can deliver.",
    "b": "Loading",
    "acs": "UA.IV.A"
  },
  {
    "s": "Chart Reading",
    "acs": "UA.II.B",
    "q": "On a sectional, a Class C segment is labeled '48' over '13'. This tells you the airspace:",
    "c": [
      "ceiling 4,800 ft MSL, floor 1,300 ft MSL",
      "ceiling 48,000 ft MSL, floor 1,300 ft MSL",
      "surface up to 4,813 ft above the ground",
      "active 48 hours over a 13-day period"
    ],
    "a": 0,
    "e": "Class C shelf numbers are hundreds of feet MSL: the top number is the ceiling and the bottom is the floor.",
    "b": "Airspace"
  },
  {
    "s": "Chart Reading",
    "acs": "UA.II.B",
    "q": "A Class B segment on a sectional reads '100' over '70'. The floor of that segment is:",
    "c": [
      "7,000 ft MSL",
      "70,000 ft MSL",
      "the surface",
      "700 ft AGL"
    ],
    "a": 0,
    "e": "Class B altitudes are hundreds of feet MSL, so 100 over 70 means a 10,000 ft MSL ceiling and a 7,000 ft MSL floor.",
    "b": "Airspace"
  },
  {
    "s": "Chart Reading",
    "acs": "UA.II.B",
    "q": "A towered airport shows a boxed number '[25]' on the sectional. This is the:",
    "c": [
      "Class D floor, 2,500 ft AGL",
      "Class D ceiling, 2,500 ft MSL",
      "field elevation of 25 ft",
      "runway length, hundreds of feet"
    ],
    "a": 1,
    "e": "A boxed number by a towered field is the Class D ceiling in hundreds of feet MSL, so [25] means surface up to 2,500 ft MSL.",
    "b": "Airspace"
  },
  {
    "s": "Chart Reading",
    "acs": "UA.II.B",
    "q": "On a sectional, Class C airspace is drawn with:",
    "c": [
      "solid magenta circles",
      "dashed magenta boundary lines",
      "solid blue circles",
      "a faded magenta vignette"
    ],
    "a": 0,
    "e": "Class C appears as solid magenta rings; Class B uses solid blue rings.",
    "b": "Airspace"
  },
  {
    "s": "Chart Reading",
    "acs": "UA.II.B",
    "q": "A dashed magenta line around an airport on a sectional marks:",
    "c": [
      "Class D airspace",
      "surface-based Class E airspace",
      "the outer Class B airspace boundary",
      "a restricted area"
    ],
    "a": 1,
    "e": "A dashed magenta line shows Class E airspace down to the surface, usually at a non-towered field with an instrument approach.",
    "b": "Airspace"
  },
  {
    "s": "Chart Reading",
    "acs": "UA.II.B",
    "q": "A dashed blue line around a towered airport on a sectional marks the boundary of:",
    "c": [
      "surface Class E airspace",
      "Class G airspace",
      "Class D airspace",
      "a warning area"
    ],
    "a": 2,
    "e": "A dashed blue line depicts Class D airspace surrounding a towered airport.",
    "b": "Airspace"
  },
  {
    "s": "Chart Reading",
    "acs": "UA.II.B",
    "q": "A fuzzy, faded magenta edge on a sectional (a magenta vignette) means Class E begins at:",
    "c": [
      "the surface",
      "1,200 ft AGL",
      "700 ft AGL",
      "18,000 ft MSL"
    ],
    "a": 2,
    "e": "The faded magenta vignette marks where the Class E floor drops to 700 ft AGL; below it is Class G.",
    "b": "Airspace"
  },
  {
    "s": "Chart Reading",
    "acs": "UA.II.B",
    "q": "A faded blue edge (a blue vignette) on a sectional indicates that Class E airspace begins at:",
    "c": [
      "60,000 ft MSL",
      "the surface",
      "1,200 ft AGL",
      "700 ft AGL"
    ],
    "a": 2,
    "e": "The faded blue vignette marks the common Class E floor of 1,200 ft AGL, with Class G below it.",
    "b": "Airspace"
  },
  {
    "s": "Chart Reading",
    "acs": "UA.II.B",
    "q": "On a sectional, an airport shown in blue rather than magenta indicates the field:",
    "c": [
      "is military only",
      "has no operating control tower at all",
      "has an operating control tower",
      "is permanently closed"
    ],
    "a": 2,
    "e": "Blue airport symbols have an operating control tower; magenta symbols are non-towered fields.",
    "b": "Airspace"
  },
  {
    "s": "Chart Reading",
    "acs": "UA.II.B",
    "q": "On a sectional, Class B and Class C are shown, respectively, as:",
    "c": [
      "dashed blue rings and dashed magenta rings",
      "identical black outlines",
      "solid blue rings and solid magenta rings",
      "two different shades of green"
    ],
    "a": 2,
    "e": "Class B is solid blue rings and Class C is solid magenta rings, an easy way to tell them apart.",
    "b": "Airspace"
  },
  {
    "s": "Under a Shelf",
    "acs": "UA.II.A",
    "q": "You plan to fly at 350 ft AGL beneath the outer shelf of Class C, whose floor there is 1,300 ft MSL. That spot is:",
    "c": [
      "inside Class C, requiring authorization first",
      "a prohibited area",
      "inside Class B airspace",
      "below the Class C shelf, not within it"
    ],
    "a": 3,
    "e": "Below the shelf's floor you are not in the Class C; you are in the airspace underneath, though still check for nearby surface areas.",
    "b": "Airspace"
  },
  {
    "s": "Class E Floor",
    "acs": "UA.II.A",
    "q": "At a site far from any airport, the Class E floor is 700 ft AGL. Flying at 350 ft AGL, you are in:",
    "c": [
      "Class E, needing prior ATC authorization",
      "Class D airspace",
      "Class B airspace",
      "Class G, needing no ATC authorization"
    ],
    "a": 3,
    "e": "Below a 700 ft AGL Class E floor the airspace is uncontrolled Class G, where Part 107 needs no ATC authorization.",
    "b": "Airspace"
  },
  {
    "s": "Class E Surface",
    "acs": "UA.II.A",
    "q": "To operate inside surface-based Class E airspace at a non-towered airport, a Part 107 pilot must:",
    "c": [
      "stay above 400 ft AGL",
      "do nothing, since it is uncontrolled",
      "get airspace authorization first",
      "file a manned flight plan"
    ],
    "a": 2,
    "e": "Surface Class E is controlled airspace, so authorization (often via LAANC) is required before operating there.",
    "b": "Airspace"
  },
  {
    "s": "VIP TFR",
    "acs": "UA.II.A",
    "q": "A Presidential (VIP) TFR typically has:",
    "c": [
      "a single 1 NM ring with no outer ring at all",
      "no size limit at all",
      "a 100 NM inner ring",
      "a 10 NM inner ring and a 30 NM outer ring"
    ],
    "a": 3,
    "e": "VIP TFRs generally set a 10 NM inner ring where flight is essentially prohibited and a 30 NM outer ring with restrictions.",
    "b": "Airspace"
  },
  {
    "s": "Restricted Area",
    "acs": "UA.II.A",
    "q": "Before flying near a charted Restricted Area, a remote pilot should:",
    "c": [
      "check NOTAMs to see if it is active",
      "enter it to save time",
      "ignore it below 400 ft",
      "assume it is always cold and inactive"
    ],
    "a": 0,
    "e": "Restricted areas are active only at certain times; check NOTAMs or the controlling agency to learn the status before flying.",
    "b": "Airspace"
  },
  {
    "s": "Under a Shelf",
    "acs": "UA.II.A",
    "q": "Flying at 300 ft AGL well away from any airport, beneath a Class E floor at 1,200 ft AGL, you are in:",
    "c": [
      "Class G airspace",
      "Class E airspace",
      "a military operations area",
      "Class C airspace"
    ],
    "a": 0,
    "e": "Beneath the 1,200 ft AGL Class E floor the airspace is Class G, where no ATC authorization is required.",
    "b": "Airspace"
  },
  {
    "s": "Warning Area",
    "acs": "UA.II.A",
    "q": "A Warning Area is charted:",
    "c": [
      "inside every Class B",
      "over international waters offshore",
      "along interstate highways",
      "only directly over major cities and towns"
    ],
    "a": 1,
    "e": "Warning Areas lie beyond 3 NM from the coast over international waters and warn of activity hazardous to aircraft.",
    "b": "Airspace"
  },
  {
    "s": "Authorization",
    "acs": "UA.II.A",
    "q": "Airspace authorization (for example through LAANC) is generally required to fly in the surface area of:",
    "c": [
      "Class B, C, D, or surface Class E",
      "every airway",
      "Class A airways",
      "any uncontrolled Class G airspace only"
    ],
    "a": 0,
    "e": "Controlled airspace down to the surface, Class B, C, D, and surface Class E, requires authorization before Part 107 flight.",
    "b": "Airspace"
  },
  {
    "s": "Class D Tower Closed",
    "acs": "UA.II.A",
    "q": "When the tower at a Class D airport closes for the night, the airspace usually:",
    "c": [
      "becomes Class B airspace",
      "stays Class D even with no tower running",
      "reverts to Class E or G",
      "closes to all flight"
    ],
    "a": 2,
    "e": "With the tower closed, Class D typically becomes Class E or G as noted in the chart supplement, changing the requirements.",
    "b": "Airspace"
  },
  {
    "s": "Sectional Currency",
    "acs": "UA.II.A",
    "q": "Airspace boundaries and floors should always be confirmed using a:",
    "c": [
      "current sectional or official app",
      "weather radar image",
      "a highway road map",
      "a years-old paper sectional chart copy"
    ],
    "a": 0,
    "e": "Airspace changes over time, so verify boundaries and floors on a current sectional or an official aeronautical app.",
    "b": "Airspace"
  },
  {
    "s": "Class E Floor",
    "acs": "UA.II.A",
    "q": "The faded magenta and faded blue edges on a sectional both mark the floor of:",
    "c": [
      "a prohibited area",
      "a Class B airspace surface boundary",
      "Class A airspace",
      "Class E, at 700 or 1,200 ft AGL"
    ],
    "a": 3,
    "e": "Both vignettes mark where Class E begins: magenta at 700 ft AGL and blue at 1,200 ft AGL, with Class G below.",
    "b": "Airspace"
  },
  {
    "s": "MOA",
    "acs": "UA.II.A",
    "q": "Planning to fly under a Military Operations Area, a remote pilot should:",
    "c": [
      "assume it is always hot and active",
      "check whether the MOA is active",
      "request a manned clearance",
      "avoid all charts"
    ],
    "a": 1,
    "e": "MOAs have scheduled active times; check NOTAMs or Flight Service so you know whether military activity is underway.",
    "b": "Airspace"
  },
  {
    "s": "Class C",
    "acs": "UA.II.A",
    "q": "To enter the surface area of Class C airspace under Part 107, you must first:",
    "c": [
      "obtain airspace authorization",
      "only monitor the tower frequency",
      "climb above 400 ft AGL",
      "squawk code 1200"
    ],
    "a": 0,
    "e": "Class C is controlled airspace; Part 107 requires prior authorization, commonly obtained through LAANC.",
    "b": "Airspace"
  },
  {
    "s": "Chart Reading",
    "acs": "UA.II.B",
    "q": "A magenta airport symbol with 'RP' notes on a sectional is a field that is:",
    "c": [
      "a fully towered field open around the clock",
      "restricted to military",
      "closed permanently",
      "non-towered with right traffic noted"
    ],
    "a": 3,
    "e": "Magenta symbols are non-towered fields; RP indicates right-hand traffic patterns for the noted runways.",
    "b": "Airspace"
  },
  {
    "s": "Vision",
    "acs": "UA.V.E",
    "q": "The most effective way to scan for other aircraft is to:",
    "c": [
      "move the eyes in small, overlapping segments",
      "stare at one fixed point",
      "sweep the whole sky in one continuous fast motion",
      "glance up only occasionally"
    ],
    "a": 0,
    "e": "A slow, systematic scan in small segments lets the eyes detect motion and traffic far better than a single fast sweep.",
    "b": "Operations"
  },
  {
    "s": "Night Vision",
    "acs": "UA.V.E",
    "q": "To see an object best at night, a pilot should:",
    "c": [
      "stare directly and steadily at it",
      "look slightly to the side of it",
      "keep one eye closed",
      "shine a bright white light"
    ],
    "a": 1,
    "e": "Central vision is weak in the dark, so off-center viewing (looking slightly to the side) reveals dim objects better.",
    "b": "Operations"
  },
  {
    "s": "Night Vision",
    "acs": "UA.V.E",
    "q": "Adapting the eyes to darkness for good night vision takes about:",
    "c": [
      "30 minutes",
      "about 2 minutes",
      "a few seconds",
      "several days"
    ],
    "a": 0,
    "e": "Full dark adaptation takes roughly 30 minutes, and exposure to bright white light quickly undoes it.",
    "b": "Operations"
  },
  {
    "s": "Vision",
    "acs": "UA.V.E",
    "q": "With nothing to focus on, such as a clear empty sky, the eyes tend to:",
    "c": [
      "relax and focus only a short distance away",
      "see distant traffic more clearly",
      "automatically stay focused sharply at infinity",
      "become far more sensitive"
    ],
    "a": 0,
    "e": "Empty-field myopia relaxes the eyes to a short focus, so deliberately focus on distant objects when scanning open sky.",
    "b": "Operations"
  },
  {
    "s": "Hyperventilation",
    "acs": "UA.V.E",
    "q": "Rapid, shallow breathing brought on by stress can cause hyperventilation, best relieved by:",
    "c": [
      "drinking coffee",
      "breathing even faster",
      "holding the breath for a full minute",
      "slowing the breathing rate"
    ],
    "a": 3,
    "e": "Hyperventilation comes from over-breathing; consciously slowing the breathing restores the balance and relieves symptoms.",
    "b": "Operations"
  },
  {
    "s": "Dehydration",
    "acs": "UA.V.E",
    "q": "Dehydration during a long operation in the sun most likely causes:",
    "c": [
      "much sharper focus and quicker reflexes",
      "stronger night vision",
      "fatigue and reduced concentration",
      "faster reflexes"
    ],
    "a": 2,
    "e": "Dehydration brings fatigue, headache, and reduced concentration, so drink water and take breaks on long, hot flights.",
    "b": "Operations"
  },
  {
    "s": "Fatigue",
    "acs": "UA.V.E",
    "q": "Acute fatigue, unlike chronic fatigue, is usually corrected by:",
    "c": [
      "ignoring it",
      "simply pushing straight through it",
      "a good rest or night's sleep",
      "more caffeine only"
    ],
    "a": 2,
    "e": "Acute fatigue is short-term and relieved by rest and sleep, while chronic fatigue builds over time and needs real recovery.",
    "b": "Operations"
  },
  {
    "s": "Attention",
    "acs": "UA.V.E",
    "q": "Fixating on the camera feed during flight can lead to:",
    "c": [
      "greatly improved overall situational awareness",
      "losing track of the aircraft and surroundings",
      "improved traffic scanning",
      "longer battery life"
    ],
    "a": 1,
    "e": "Channelized attention on the camera can cause a loss of aircraft position and airspace awareness; keep scanning outside.",
    "b": "Operations"
  },
  {
    "s": "Vision",
    "acs": "UA.V.E",
    "q": "Because it takes time to see and react to other traffic, a pilot should:",
    "c": [
      "rely only on the sound of engines",
      "scan continuously, not just once",
      "look only at takeoff",
      "assume the sky is clear"
    ],
    "a": 1,
    "e": "Detecting and reacting to traffic takes time, so scan the sky continuously rather than only once or by sound.",
    "b": "Operations"
  },
  {
    "s": "Night Vision",
    "acs": "UA.V.E",
    "q": "At night a pilot's sense of the drone's position is reduced, so they should:",
    "c": [
      "ignore the anti-collision light",
      "fly much faster to compensate for the dark",
      "skip the preflight check",
      "rely more on lights and known references"
    ],
    "a": 3,
    "e": "With poor depth cues at night, use the anti-collision light and known ground references to keep track of the aircraft.",
    "b": "Operations"
  },
  {
    "s": "Traffic Pattern",
    "acs": "UA.V.B",
    "q": "Standard airport traffic patterns for manned aircraft use:",
    "c": [
      "right-hand turns at all airports always",
      "no set direction",
      "left turns unless noted otherwise",
      "vertical climbs only"
    ],
    "a": 2,
    "e": "Traffic patterns are flown with left turns unless a right pattern is charted, so anticipate manned traffic turning left.",
    "b": "Operations"
  },
  {
    "s": "Non-Towered Airport",
    "acs": "UA.V.B",
    "q": "Operating near a non-towered airport, a remote pilot should:",
    "c": [
      "monitor CTAF and stay clear of traffic",
      "enter the active runway",
      "climb into the pattern",
      "broadcast a continuous mayday call on 121.5"
    ],
    "a": 0,
    "e": "Monitor the common traffic advisory frequency for position reports and keep well clear of the manned traffic flow.",
    "b": "Operations"
  },
  {
    "s": "Airport Operations",
    "acs": "UA.V.B",
    "q": "Near an airport, a small unmanned aircraft must:",
    "c": [
      "fly in the traffic pattern",
      "not interfere with manned operations",
      "land on the runway",
      "always keep the right of way over them"
    ],
    "a": 1,
    "e": "A drone must never interfere with airport traffic and must yield to manned aircraft at all times.",
    "b": "Operations"
  },
  {
    "s": "See and Avoid",
    "acs": "UA.V.B",
    "q": "Manned aircraft are most concentrated:",
    "c": [
      "above 10,000 ft only",
      "near airports and in the pattern",
      "inside restricted areas",
      "only far out over the open ocean waters"
    ],
    "a": 1,
    "e": "Manned traffic gathers around airports and in the traffic pattern, so use extra vigilance when operating nearby.",
    "b": "Operations"
  },
  {
    "s": "Right-of-Way",
    "acs": "UA.V.B",
    "q": "If a crop duster or helicopter is working near your low-altitude site, you should:",
    "c": [
      "yield and keep well clear of it",
      "hold your altitude",
      "race it to the spot",
      "assume that it can always see you"
    ],
    "a": 0,
    "e": "Yield and stay well clear; low-working manned aircraft may not see a small drone, so separation is your responsibility.",
    "b": "Operations"
  },
  {
    "s": "Task Saturation",
    "acs": "UA.V.D",
    "q": "When too many tasks pile up at once (task saturation), the best response is to:",
    "c": [
      "add more tasks",
      "stop scanning",
      "shed nonessential tasks and fly the aircraft",
      "try to speed absolutely everything up at once"
    ],
    "a": 2,
    "e": "Under task saturation, drop nonessential tasks and prioritize controlling the aircraft to keep the flight safe.",
    "b": "Operations"
  },
  {
    "s": "CRM",
    "acs": "UA.V.D",
    "q": "During takeoff, landing, and other critical moments, the crew should:",
    "c": [
      "check social media",
      "chat freely about anything at all",
      "avoid nonessential conversation",
      "split their attention"
    ],
    "a": 2,
    "e": "Keeping communication sterile during critical phases prevents distraction and keeps attention on the operation.",
    "b": "Operations"
  },
  {
    "s": "Distraction",
    "acs": "UA.V.D",
    "q": "To limit distraction in flight, camera and app settings are best adjusted:",
    "c": [
      "while hovering right over people",
      "on the ground before launch",
      "mid-turn at low altitude",
      "during a fast descent"
    ],
    "a": 1,
    "e": "Set up shots and settings on the ground so attention stays on flying once airborne.",
    "b": "Operations"
  },
  {
    "s": "Situational Awareness",
    "acs": "UA.V.D",
    "q": "Maintaining situational awareness means continuously tracking:",
    "c": [
      "just the camera image",
      "the aircraft, airspace, and nearby people",
      "only the remaining battery level in percent",
      "yesterday's weather"
    ],
    "a": 1,
    "e": "Situational awareness is an ongoing picture of the aircraft, the airspace, obstacles, and people around the operation.",
    "b": "Operations"
  },
  {
    "s": "External Pressure",
    "acs": "UA.V.D",
    "q": "Continuing a flight into worsening conditions just to finish the job is an example of:",
    "c": [
      "get-there-itis, a dangerous pressure",
      "careful and thorough preflight planning",
      "good airmanship",
      "a required procedure"
    ],
    "a": 0,
    "e": "Get-there-itis is the pressure to complete a mission despite mounting risk; recognize it and be willing to stop.",
    "b": "Operations"
  },
  {
    "s": "Automation",
    "acs": "UA.V.D",
    "q": "Return-to-home and GPS position hold are helpful, but a pilot should:",
    "c": [
      "be ready to take manual control",
      "trust them completely at all times",
      "never watch the aircraft",
      "disable all failsafes"
    ],
    "a": 0,
    "e": "Automation can fail or behave unexpectedly, so stay ready to fly manually and keep watching the aircraft.",
    "b": "Operations"
  },
  {
    "s": "Emergency",
    "acs": "UA.V.D",
    "q": "If the aircraft suddenly behaves unexpectedly, the pilot's first priority is to:",
    "c": [
      "post about it online",
      "keep control and move away from people",
      "immediately land on the nearest busy road",
      "speed up and climb"
    ],
    "a": 1,
    "e": "Fly the aircraft first: maintain control and increase distance from people while working the problem.",
    "b": "Operations"
  },
  {
    "s": "Resource Management",
    "acs": "UA.V.D",
    "q": "Using checklists, apps, and a visual observer to manage workload is:",
    "c": [
      "only for big crews",
      "good resource management",
      "strictly against the Part 107 rules",
      "a waste of time"
    ],
    "a": 1,
    "e": "Drawing on checklists, tools, and crew is sound single-pilot resource management that lowers workload and risk.",
    "b": "Operations"
  },
  {
    "s": "Error Chain",
    "acs": "UA.V.D",
    "q": "Recognizing that small mistakes can link into an accident, a pilot should:",
    "c": [
      "ignore minor slips",
      "break the chain by fixing errors early",
      "only start worrying after landing safely",
      "assume luck will hold"
    ],
    "a": 1,
    "e": "Most accidents come from a chain of small errors; catching and fixing one link early prevents the outcome.",
    "b": "Operations"
  },
  {
    "s": "Altitude Limit",
    "acs": "UA.I.B",
    "q": "You are inspecting a 200-ft tower. Under Part 107 you may legally climb to about:",
    "c": [
      "400 ft AGL and no higher than that at all",
      "600 ft AGL, within 400 ft of the tower",
      "1,000 ft AGL over the tower",
      "900 ft AGL anywhere nearby"
    ],
    "a": 1,
    "e": "Within 400 ft of a structure you may fly up to 400 ft above its top, so a 200-ft tower allows about 600 ft AGL.",
    "b": "Regulations"
  },
  {
    "s": "Altitude Limit",
    "acs": "UA.I.B",
    "q": "The exception that lets a drone exceed 400 ft AGL applies only when the aircraft:",
    "c": [
      "carries no payload",
      "stays within 400 ft of a structure",
      "is flown after sunset",
      "is flown out over open farmland fields"
    ],
    "a": 1,
    "e": "You may exceed 400 ft AGL only within a 400-ft lateral distance of a structure, remaining within 400 ft of its uppermost limit.",
    "b": "Regulations"
  },
  {
    "s": "Altitude Limit",
    "acs": "UA.I.B",
    "q": "The Part 107 400-ft altitude limit is normally measured:",
    "c": [
      "from mean sea level",
      "measured from the nearest airport elevation",
      "from the operator's height",
      "above the ground below the aircraft"
    ],
    "a": 3,
    "e": "The 400-ft ceiling is above ground level, measured from the surface below, except near a structure where it is measured from the structure.",
    "b": "Regulations"
  },
  {
    "s": "Civil Twilight",
    "acs": "UA.I.B",
    "q": "Civil twilight for Part 107 in the lower 48 states runs from about:",
    "c": [
      "1 hour after sunrise to 1 hour before sunset",
      "sunrise to sunset only",
      "30 min before sunrise to 30 min after sunset",
      "noon to midnight"
    ],
    "a": 2,
    "e": "Civil twilight is roughly the 30 minutes before official sunrise and the 30 minutes after official sunset.",
    "b": "Regulations"
  },
  {
    "s": "Civil Twilight",
    "acs": "UA.I.B",
    "q": "Anti-collision lighting is required for Part 107 operations at night and during:",
    "c": [
      "calm winds",
      "civil twilight",
      "clear daylight",
      "high visibility"
    ],
    "a": 1,
    "e": "Operations at night and in civil twilight require anti-collision lighting; daylight operations do not.",
    "b": "Regulations"
  },
  {
    "s": "Night Lighting",
    "acs": "UA.I.B",
    "q": "The anti-collision lighting required for night operations must be visible for at least:",
    "c": [
      "1 statute mile",
      "10 statute miles",
      "300 feet",
      "3 statute miles"
    ],
    "a": 3,
    "e": "The required anti-collision lighting must be visible for at least 3 statute miles and flash at a rate that helps avoid a collision.",
    "b": "Regulations"
  },
  {
    "s": "Change of Address",
    "acs": "UA.I.A",
    "q": "After moving, a remote pilot must report a permanent mailing address change to the FAA within:",
    "c": [
      "2 years",
      "30 days",
      "10 days",
      "24 hours"
    ],
    "a": 1,
    "e": "A certificate holder must notify the FAA of a permanent mailing address change within 30 days to keep exercising privileges.",
    "b": "Regulations"
  },
  {
    "s": "Accident Reporting",
    "acs": "UA.I.C",
    "q": "For the $500 accident-reporting threshold, the damage counted is:",
    "c": [
      "only injuries, never property",
      "controller damage only",
      "only damage to the drone aircraft, nothing else",
      "damage to property other than the aircraft"
    ],
    "a": 3,
    "e": "The report is required at $500 or more of damage to property other than the small unmanned aircraft, or for a serious injury.",
    "b": "Regulations"
  },
  {
    "s": "Physical Condition",
    "acs": "UA.I.A",
    "q": "Part 107 requires no FAA medical certificate, but a remote pilot may not fly if they:",
    "c": [
      "have a condition that impairs safe flight",
      "are over age 60",
      "recently skipped a full breakfast that morning",
      "wear corrective lenses"
    ],
    "a": 0,
    "e": "Under 107.17 you may not operate if you know or have reason to know of a physical or mental condition that would interfere with safe operation.",
    "b": "Regulations"
  },
  {
    "s": "Eligibility",
    "acs": "UA.I.A",
    "q": "Before being issued a remote pilot certificate, an applicant must pass:",
    "c": [
      "a flight physical exam",
      "a vision-only screening",
      "a TSA security background check",
      "a full manned-aircraft flight checkride"
    ],
    "a": 2,
    "e": "Applicants must be vetted by the TSA (a security background check) in addition to passing the knowledge test.",
    "b": "Regulations"
  },
  {
    "s": "Waivers",
    "acs": "UA.I.D",
    "q": "Which core Part 107 rule can be waived if you show it can be done safely?",
    "c": [
      "the ban on careless or reckless operation",
      "the registration requirement",
      "the visual-line-of-sight requirement",
      "the Remote ID requirement"
    ],
    "a": 2,
    "e": "Visual line of sight (107.31) is among the waivable rules; registration, Remote ID, and careless operation are not waivable.",
    "b": "Regulations"
  },
  {
    "s": "Waivers",
    "acs": "UA.I.D",
    "q": "A drone that cannot broadcast Remote ID and has no module:",
    "c": [
      "may fly anywhere below 400 ft",
      "must be flown only within a FRIA",
      "is exempt from all rules",
      "can apply for a Remote ID waiver instead"
    ],
    "a": 1,
    "e": "The Remote ID requirement cannot be waived; such a drone may only operate within an FAA-Recognized Identification Area (FRIA).",
    "b": "Regulations"
  },
  {
    "s": "Waivers",
    "acs": "UA.I.D",
    "q": "The FAA will grant a Part 107 waiver only if the applicant shows the operation can be conducted with:",
    "c": [
      "the absolute lowest possible cost",
      "an equivalent level of safety",
      "a manned chase plane",
      "no paperwork at all"
    ],
    "a": 1,
    "e": "A waiver is issued only when the proposed operation can be conducted safely, at an equivalent level of safety to the rule.",
    "b": "Regulations"
  },
  {
    "s": "Waivers",
    "acs": "UA.I.D",
    "q": "A Certificate of Waiver issued by the FAA:",
    "c": [
      "may include specific conditions and limits",
      "removes all Part 107 rules",
      "never expires or changes",
      "applies to every drone pilot in the nation"
    ],
    "a": 0,
    "e": "A waiver authorizes deviation from specific rules and typically comes with conditions and limitations the pilot must follow.",
    "b": "Regulations"
  },
  {
    "s": "Waivers",
    "acs": "UA.I.D",
    "q": "A Part 107 Certificate of Waiver authorizes:",
    "c": [
      "all pilots at that airport",
      "unlimited future flights anywhere, anytime",
      "any operation the pilot wants",
      "only the specific operation it describes"
    ],
    "a": 3,
    "e": "A waiver is specific to the operation described in the application and does not grant blanket permission for other flights.",
    "b": "Regulations"
  },
  {
    "s": "Knowledge Test",
    "acs": "UA.I.A",
    "q": "The Part 107 initial aeronautical knowledge test consists of:",
    "c": [
      "60 multiple-choice questions",
      "a live in-person flight demonstration",
      "25 true-or-false questions",
      "200 essay questions"
    ],
    "a": 0,
    "e": "The initial knowledge test has 60 multiple-choice questions, and a score of 70 percent is required to pass.",
    "b": "Regulations"
  },
  {
    "s": "Applicability",
    "acs": "UA.I.B",
    "q": "Flying a small drone entirely indoors is:",
    "c": [
      "allowed only with a waiver",
      "still strictly capped at the 400 ft AGL limit",
      "a Remote ID violation",
      "generally outside FAA Part 107 rules"
    ],
    "a": 3,
    "e": "Part 107 governs operations in the outdoor National Airspace System, so fully indoor flight is generally not subject to it.",
    "b": "Regulations"
  },
  {
    "s": "Preflight",
    "acs": "UA.I.B",
    "q": "The preflight familiarization required by 107.49 includes assessing:",
    "c": [
      "the aircraft color scheme",
      "local weather, airspace, and the site",
      "only the battery charge and nothing else",
      "the client's schedule"
    ],
    "a": 1,
    "e": "Before flight the remote PIC must assess the operating area, weather, airspace, hazards, aircraft condition, and crew readiness.",
    "b": "Regulations"
  },
  {
    "s": "Registration",
    "acs": "UA.I.F",
    "q": "Under Part 107, registration is required for a small unmanned aircraft:",
    "c": [
      "only if flown for pay",
      "regardless of its weight",
      "only in controlled airspace",
      "only above 55 lb"
    ],
    "a": 1,
    "e": "Every drone flown under Part 107 must be registered regardless of weight; the 0.55 lb threshold applies to recreational flyers.",
    "b": "Regulations"
  },
  {
    "s": "Registration",
    "acs": "UA.I.F",
    "q": "You fly three different drones commercially. Under Part 107 you must:",
    "c": [
      "register each aircraft separately",
      "use a single number for all three",
      "register just one of them",
      "skip registration entirely"
    ],
    "a": 0,
    "e": "Part 107 registration is per aircraft, so each drone is registered individually and carries its own registration number.",
    "b": "Regulations"
  },
  {
    "s": "Accident Reporting",
    "acs": "UA.I.C",
    "q": "A reportable Part 107 accident is filed with the FAA through:",
    "c": [
      "the FAA DroneZone website",
      "a local police report",
      "the aircraft manufacturer",
      "a social media post"
    ],
    "a": 0,
    "e": "Reportable accidents are submitted to the FAA, for example through the FAA DroneZone site, within 10 calendar days.",
    "b": "Regulations"
  },
  {
    "s": "Waivers",
    "acs": "UA.I.D",
    "q": "To fly a pipeline survey beyond visual line of sight, a remote pilot needs:",
    "c": [
      "a recreational TRUST pass",
      "nothing more than a basic certificate",
      "a Part 107 waiver for that operation",
      "only a visual observer"
    ],
    "a": 2,
    "e": "Beyond-visual-line-of-sight flight deviates from 107.31, so it requires an approved Part 107 waiver for that operation.",
    "b": "Regulations"
  },
  {
    "s": "Over People",
    "acs": "UA.I.D",
    "q": "To conduct sustained flight directly over a crowd at an outdoor concert, a remote pilot needs:",
    "c": [
      "an over-people category or a waiver",
      "just the client's permission",
      "nothing, if under 400 ft",
      "only a very bright anti-collision light"
    ],
    "a": 0,
    "e": "Sustained flight over people not involved requires meeting an approved over-people category or holding a waiver.",
    "b": "Regulations"
  },
  {
    "s": "Certificate",
    "acs": "UA.I.A",
    "q": "A remote pilot certificate obtained under Part 107:",
    "c": [
      "expires exactly two years after issue",
      "must be renewed by re-taking the initial test",
      "stays valid but needs recurrent training",
      "converts to a manned license"
    ],
    "a": 2,
    "e": "The certificate itself does not expire, but the holder must complete recurrent training every 24 calendar months to keep exercising privileges.",
    "b": "Regulations"
  },
  {
    "s": "Scale",
    "q": "On a VFR sectional (1:500,000), one inch on the chart equals about:",
    "c": [
      "6.9 nautical miles",
      "half a nautical mile",
      "70 nautical miles",
      "1 nautical mile"
    ],
    "a": 0,
    "e": "At 1:500,000, one inch represents 500,000 inches on the ground, which is about 6.9 nautical miles.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Scale",
    "q": "One degree of latitude on a sectional chart equals:",
    "c": [
      "60 nautical miles",
      "1 nautical mile",
      "6 nautical miles",
      "600 nautical miles"
    ],
    "a": 0,
    "e": "Each degree of latitude spans 60 minutes, and since one minute equals one nautical mile, a degree is 60 nautical miles.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Scale",
    "q": "The easiest built-in way to measure distance on a sectional is to use:",
    "c": [
      "the airport data block",
      "the latitude scale on the side",
      "the chart's title panel",
      "the color of the surrounding terrain"
    ],
    "a": 1,
    "e": "One minute of latitude equals one nautical mile, so the latitude scale along the chart edge works as a distance ruler.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Coordinates",
    "q": "On the globe, latitude and longitude are measured, respectively:",
    "c": [
      "by terrain color only",
      "E/W of the equator and N/S of the poles instead",
      "N/S of the equator, E/W of the prime meridian",
      "only in statute miles"
    ],
    "a": 2,
    "e": "Latitude is measured north or south of the equator, and longitude east or west of the prime meridian.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Coordinates",
    "q": "Across the continental United States, lines of longitude have values that:",
    "c": [
      "stay the same everywhere",
      "increase toward the west",
      "increase toward the east",
      "are measured in feet"
    ],
    "a": 1,
    "e": "In the continental US, longitude increases going westward, for example from about 75 degrees W to 120 degrees W.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Coordinates",
    "q": "The small tick marks along the latitude and longitude lines on a sectional are spaced:",
    "c": [
      "one minute apart",
      "ten minutes apart",
      "one degree apart",
      "one mile apart"
    ],
    "a": 0,
    "e": "The ticks are spaced at one-minute intervals, and one minute of latitude conveniently equals one nautical mile.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Airport Data",
    "q": "In a sectional airport data block, a number such as 1204 alone usually gives the:",
    "c": [
      "the traffic pattern altitude",
      "tower frequency",
      "runway heading",
      "field elevation in feet MSL"
    ],
    "a": 3,
    "e": "The standalone number in a data block is the field elevation in feet above mean sea level.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Airport Data",
    "q": "In an airport data block, a runway length shown as 72 means the longest runway is:",
    "c": [
      "72 feet long",
      "7,200 feet long",
      "720 feet long",
      "72 nautical miles"
    ],
    "a": 1,
    "e": "Runway length in a data block is given in hundreds of feet, so 72 means 7,200 feet.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Airport Data",
    "q": "On a sectional, a common traffic advisory frequency is marked with:",
    "c": [
      "a circled letter C",
      "a circled letter H",
      "a magenta flag",
      "a bold star"
    ],
    "a": 0,
    "e": "A solid dot with a circled C next to a frequency identifies the CTAF used for self-announced position reports.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Airport Data",
    "q": "A frequency of 122.8 listed at a non-towered airport is typically the:",
    "c": [
      "the main ATC clearance frequency",
      "weather-only frequency",
      "emergency frequency",
      "UNICOM advisory frequency"
    ],
    "a": 3,
    "e": "122.8 is a common UNICOM frequency at non-towered airports, used for advisories and often as the CTAF.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Airport Data",
    "q": "In an airport data block, 'RP' followed by runway numbers indicates:",
    "c": [
      "right traffic for those runways",
      "a private helipad",
      "a restricted airport",
      "a required parachute jumping area"
    ],
    "a": 0,
    "e": "RP means a right-hand traffic pattern is in use for the listed runways, opposite the standard left pattern.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Airport Data",
    "q": "An asterisk before the letter L (\"*L\") in an airport data block means the runway lighting is:",
    "c": [
      "never available",
      "laser-based",
      "always much brighter than normal lighting",
      "limited, part-time, or pilot-controlled"
    ],
    "a": 3,
    "e": "The asterisk shows lighting limitations such as part-time or pilot-controlled operation; check the chart supplement.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Obstacles",
    "q": "On a sectional, the highest obstacle on that chart is printed:",
    "c": [
      "in bold, larger numbers",
      "in tiny faded gray-colored text",
      "in green ink",
      "without any height"
    ],
    "a": 0,
    "e": "The single highest charted obstacle is shown in bold, oversized numbers to draw the pilot's attention.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Obstacles",
    "q": "Obstacles less than 1,000 ft AGL and those 1,000 ft AGL or higher are shown with:",
    "c": [
      "exactly the same symbol always",
      "different obstruction symbols",
      "no symbol at all",
      "only a dashed line"
    ],
    "a": 1,
    "e": "Charts use one symbol for obstacles under 1,000 ft AGL and a taller, different symbol for those 1,000 ft AGL and above.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Navigation",
    "q": "On a sectional, a VOR's frequency and identifier are printed:",
    "c": [
      "inside the nearest airport symbol",
      "in a box near the compass rose",
      "on the chart cover only",
      "along the nearest airway"
    ],
    "a": 1,
    "e": "Each VOR shows its name, frequency, and Morse identifier in a small box beside its compass rose.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Navigation",
    "q": "A runway numbered 09 is aligned to a magnetic heading of about:",
    "c": [
      "090 degrees",
      "900 degrees",
      "9 degrees",
      "190 degrees"
    ],
    "a": 0,
    "e": "Runway numbers are the magnetic heading with the last digit dropped, so runway 09 points to about 090 degrees.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Time",
    "q": "A chart note or report gives a time of 1800Z. In Eastern Standard Time (UTC minus 5), that is:",
    "c": [
      "0600 local",
      "2300 local",
      "1300 local",
      "1800 local"
    ],
    "a": 2,
    "e": "Zulu time is UTC, so subtract five hours for Eastern Standard Time: 1800Z becomes 1300 local.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Terrain",
    "q": "On a sectional's graduated color tints, the highest terrain is shown by:",
    "c": [
      "no color at all",
      "the darkest tint",
      "the lightest tint",
      "a blue tint"
    ],
    "a": 1,
    "e": "Terrain tints darken as elevation rises, so the darkest browns mark the highest ground on the chart.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Navigation",
    "q": "A line on a sectional along which magnetic variation is zero is called:",
    "c": [
      "an isogonic line",
      "a Victor airway",
      "a parallel",
      "an agonic line"
    ],
    "a": 3,
    "e": "An agonic line connects points of zero magnetic variation, where magnetic north and true north align.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Scale",
    "q": "Distances on aeronautical sectional charts are normally expressed in:",
    "c": [
      "metric kilometers",
      "feet",
      "city blocks",
      "nautical miles"
    ],
    "a": 3,
    "e": "Aeronautical charts and navigation use nautical miles, matching one minute of latitude to one nautical mile.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Navigation",
    "q": "To measure the length of a planned leg on a sectional, a pilot commonly uses:",
    "c": [
      "a plotter against the latitude scale",
      "the terrain color key",
      "the chart's border notes",
      "the nearest airport's radio frequency box"
    ],
    "a": 0,
    "e": "A plotter or ruler compared to the latitude scale (one minute equals one nautical mile) gives the leg distance.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Coordinates",
    "q": "Latitude and longitude on a sectional are labeled in:",
    "c": [
      "degrees and minutes",
      "feet and inches",
      "statute miles and yards",
      "hours and seconds"
    ],
    "a": 0,
    "e": "Coordinates are given in degrees and minutes (and sometimes seconds), letting a pilot pinpoint a location.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Airport Data",
    "q": "Manned aircraft near a small airport usually fly a traffic pattern at about:",
    "c": [
      "400 ft MSL",
      "50 ft AGL",
      "1,000 ft AGL",
      "10,000 ft AGL"
    ],
    "a": 2,
    "e": "Typical light-aircraft patterns are near 1,000 ft AGL, so a drone pilot should stay well clear of that altitude near airports.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Airport Data",
    "q": "A sectional airport data block generally lists the airport name, its elevation, and the:",
    "c": [
      "the pilot's home address",
      "the current local weather forecast",
      "common traffic or tower frequency",
      "fuel prices"
    ],
    "a": 2,
    "e": "The data block packs the airport name, field elevation, lighting, longest runway, and the CTAF or tower frequency.",
    "acs": "UA.II.B",
    "b": "Charts"
  },
  {
    "s": "Remote ID",
    "acs": "UA.I.F",
    "q": "A standard Remote ID drone broadcasts the control station location, while a broadcast module instead sends the:",
    "c": [
      "manufacturer's address",
      "take-off location",
      "landing location",
      "home airport location"
    ],
    "a": 1,
    "e": "A broadcast module transmits the take-off location, whereas standard Remote ID transmits the control station location.",
    "b": "Regulations"
  },
  {
    "s": "Remote ID",
    "acs": "UA.I.F",
    "q": "Remote ID meets its requirement by:",
    "c": [
      "emailing a flight log",
      "calling ATC by phone",
      "streaming continuously over a cellular network",
      "broadcasting over radio, no internet needed"
    ],
    "a": 3,
    "e": "Remote ID is a local radio broadcast (such as Bluetooth or Wi-Fi); it does not need an internet or cellular connection.",
    "b": "Regulations"
  },
  {
    "s": "Remote ID",
    "acs": "UA.I.F",
    "q": "Remote ID must broadcast during which part of the flight?",
    "c": [
      "only during the take-off roll",
      "from take-off to shutdown",
      "only when above 400 ft",
      "only near airports"
    ],
    "a": 1,
    "e": "The broadcast must run for the entire operation, from take-off until the aircraft shuts down.",
    "b": "Regulations"
  },
  {
    "s": "Remote ID",
    "acs": "UA.I.F",
    "q": "The Remote ID rule applies to a drone that:",
    "c": [
      "is flown only indoors",
      "weighs under 250 grams and nothing more",
      "is required to be registered",
      "has a camera"
    ],
    "a": 2,
    "e": "Remote ID applies to drones that must be registered; under Part 107 that means essentially every aircraft.",
    "b": "Regulations"
  },
  {
    "s": "Visual Line of Sight",
    "acs": "UA.I.B",
    "q": "To satisfy the visual-line-of-sight rule, the remote PIC may use:",
    "c": [
      "a telescope on a tripod",
      "glasses or contacts, but not binoculars",
      "powerful binoculars to greatly extend the view",
      "a first-person-view headset alone"
    ],
    "a": 1,
    "e": "Line of sight must be met with unaided vision, corrective lenses allowed; binoculars or an FPV headset do not satisfy it.",
    "b": "Regulations"
  },
  {
    "s": "Visual Line of Sight",
    "acs": "UA.I.B",
    "q": "Under Part 107, the remote PIC ___ keep the aircraft within visual line of sight.",
    "c": [
      "should usually",
      "may occasionally",
      "is advised to",
      "must always"
    ],
    "a": 3,
    "e": "Visual line of sight is a firm requirement (must), not a recommendation, unless a waiver says otherwise.",
    "b": "Regulations"
  },
  {
    "s": "Over People",
    "acs": "UA.I.B",
    "q": "A small UAS ___ be flown over a person not participating unless an approved category or waiver applies.",
    "c": [
      "should sometimes",
      "may freely",
      "must always",
      "may not"
    ],
    "a": 3,
    "e": "Flight over non-participating people is prohibited unless the aircraft meets an over-people category or holds a waiver.",
    "b": "Regulations"
  },
  {
    "s": "Night Operations",
    "acs": "UA.I.B",
    "q": "For Part 107 operations at night, anti-collision lighting is:",
    "c": [
      "optional",
      "required",
      "discouraged",
      "recommended"
    ],
    "a": 1,
    "e": "Anti-collision lighting visible for 3 statute miles is required at night, not merely recommended.",
    "b": "Regulations"
  },
  {
    "s": "Moving Vehicle",
    "acs": "UA.I.B",
    "q": "Operating the control station from a moving vehicle is allowed only over a ___ area.",
    "c": [
      "densely populated city",
      "sparsely populated",
      "heavily trafficked",
      "congested urban"
    ],
    "a": 1,
    "e": "Operating from a moving vehicle is permitted only over sparsely populated areas, unless a waiver allows otherwise.",
    "b": "Regulations"
  },
  {
    "s": "Right-of-Way",
    "acs": "UA.I.B",
    "q": "When a manned aircraft approaches, the remote PIC:",
    "c": [
      "yields only if convenient",
      "may hold its altitude if it is higher",
      "must yield the right of way",
      "has the right of way"
    ],
    "a": 2,
    "e": "The remote PIC must always give way to manned aircraft, yielding the right of way and staying clear.",
    "b": "Regulations"
  },
  {
    "s": "Careless Operation",
    "acs": "UA.I.D",
    "q": "The prohibition on careless or reckless operation is:",
    "c": [
      "waivable with a good reason",
      "waived automatically at night",
      "only a guideline",
      "a rule that cannot be waived"
    ],
    "a": 3,
    "e": "The ban on careless or reckless operation is a core rule that is not waivable under Part 107.",
    "b": "Regulations"
  },
  {
    "s": "Authorization vs Waiver",
    "acs": "UA.I.D",
    "q": "Permission to enter controlled airspace is called an airspace ___, not a waiver.",
    "c": [
      "exemption",
      "registration",
      "certification",
      "authorization"
    ],
    "a": 3,
    "e": "An airspace authorization grants access to controlled airspace; a waiver instead permits deviation from a specific rule.",
    "b": "Regulations"
  },
  {
    "s": "Registration",
    "acs": "UA.I.F",
    "q": "A drone flown under Part 107 must be registered:",
    "c": [
      "after 10 flights",
      "before its first flight",
      "only if it crashes",
      "within 30 days after flying"
    ],
    "a": 1,
    "e": "Registration must be completed before the aircraft's first flight, not afterward.",
    "b": "Regulations"
  },
  {
    "s": "Registration",
    "acs": "UA.I.F",
    "q": "The registration number on the aircraft must be:",
    "c": [
      "concealed inside the battery bay only",
      "visible only under UV light",
      "engraved on the propeller",
      "legible and readable without tools"
    ],
    "a": 3,
    "e": "The number must be marked on an exterior surface and readable without tools or opening any compartment.",
    "b": "Regulations"
  },
  {
    "s": "Accident Reporting",
    "acs": "UA.I.C",
    "q": "The $500 accident-reporting threshold counts damage to property:",
    "c": [
      "only to the aircraft",
      "only to the controller",
      "other than the aircraft itself",
      "including the small aircraft itself"
    ],
    "a": 2,
    "e": "The threshold is $500 or more of damage to property other than the small unmanned aircraft.",
    "b": "Regulations"
  },
  {
    "s": "Accident Reporting",
    "acs": "UA.I.C",
    "q": "A reportable Part 107 accident must be reported to the FAA within:",
    "c": [
      "24 hours",
      "10 business hours",
      "30 days",
      "10 calendar days"
    ],
    "a": 3,
    "e": "A reportable accident must be filed with the FAA within 10 calendar days of the event.",
    "b": "Regulations"
  },
  {
    "s": "Drugs and Alcohol",
    "acs": "UA.I.A",
    "q": "Part 107 bars operating within how many hours of consuming alcohol?",
    "c": [
      "12 hours",
      "2 hours",
      "24 hours",
      "8 hours"
    ],
    "a": 3,
    "e": "A pilot may not operate within 8 hours of consuming alcohol, and never while impaired.",
    "b": "Regulations"
  },
  {
    "s": "Drugs and Alcohol",
    "acs": "UA.I.A",
    "q": "A remote pilot may not operate with a blood alcohol concentration at or above:",
    "c": [
      "0.08 percent",
      "0.04 percent",
      "0.02 percent",
      "0.10 percent"
    ],
    "a": 1,
    "e": "The limit is a blood alcohol concentration of 0.04 percent or higher, lower than most driving limits.",
    "b": "Regulations"
  },
  {
    "s": "Altitude Limit",
    "acs": "UA.I.B",
    "q": "The 400-foot Part 107 altitude limit is normally measured in feet:",
    "c": [
      "above the nearest airport",
      "above the operator's head",
      "above ground level",
      "above mean sea level"
    ],
    "a": 2,
    "e": "The 400-foot ceiling is above ground level, except that near a structure it is measured from the structure.",
    "b": "Regulations"
  },
  {
    "s": "Operating Limits",
    "acs": "UA.I.B",
    "q": "The maximum groundspeed allowed under Part 107 is:",
    "c": [
      "150 mph (130 knots)",
      "200 mph (174 knots)",
      "55 mph (48 knots)",
      "100 mph (87 knots)"
    ],
    "a": 3,
    "e": "Groundspeed is limited to 100 mph, which is 87 knots.",
    "b": "Regulations"
  },
  {
    "s": "Operating Limits",
    "acs": "UA.I.B",
    "q": "The minimum flight visibility for Part 107, measured from the control station, is:",
    "c": [
      "3 statute miles",
      "half a statute mile",
      "1 statute mile",
      "5 statute miles"
    ],
    "a": 0,
    "e": "A minimum of 3 statute miles of flight visibility is required from the control station.",
    "b": "Regulations"
  },
  {
    "s": "Operating Limits",
    "acs": "UA.I.B",
    "q": "Part 107 cloud clearance is at least 500 ft below a cloud and how far horizontally?",
    "c": [
      "250 ft",
      "2,000 ft",
      "500 ft",
      "1,000 ft"
    ],
    "a": 1,
    "e": "The requirement is 500 feet below and 2,000 feet horizontal from clouds.",
    "b": "Regulations"
  },
  {
    "s": "Responsibility",
    "acs": "UA.I.A",
    "q": "Final responsibility and authority for a Part 107 operation rests with the:",
    "c": [
      "visual observer",
      "remote pilot in command",
      "FAA inspector",
      "small aircraft's manufacturer"
    ],
    "a": 1,
    "e": "The remote pilot in command is directly responsible for, and the final authority over, the operation.",
    "b": "Regulations"
  },
  {
    "s": "Currency",
    "acs": "UA.I.A",
    "q": "To keep exercising Part 107 privileges, recurrent training is:",
    "c": [
      "optional after the first test",
      "required only once ever",
      "required every 24 calendar months",
      "recommended every couple of years or so"
    ],
    "a": 2,
    "e": "Recurrent training is required every 24 calendar months to continue exercising remote pilot privileges.",
    "b": "Regulations"
  },
  {
    "s": "Over People",
    "acs": "UA.I.B",
    "q": "A Category 2 small UAS over people must not cause an injury worse than the impact of:",
    "c": [
      "1 ft-lb of kinetic energy",
      "11 ft-lb of kinetic energy",
      "25 ft-lb of kinetic energy",
      "50 ft-lb of kinetic energy"
    ],
    "a": 1,
    "e": "Category 2 aircraft must not, on impact, transfer more than 11 ft-lb of kinetic energy, with no lacerations and no exposed rotating parts.",
    "b": "Regulations"
  },
  {
    "s": "Over People",
    "acs": "UA.I.B",
    "q": "The kinetic-energy injury limit for a Category 3 small UAS over people is:",
    "c": [
      "5 ft-lb",
      "25 ft-lb",
      "100 ft-lb",
      "11 ft-lb"
    ],
    "a": 1,
    "e": "Category 3 aircraft have a higher injury limit of 25 ft-lb but come with tighter operating-site restrictions.",
    "b": "Regulations"
  },
  {
    "s": "Over People",
    "acs": "UA.I.B",
    "q": "Unlike Category 2, a Category 3 operation may NOT be flown:",
    "c": [
      "with a visual observer",
      "anywhere near any tall city building",
      "after sunrise",
      "over an open-air assembly of people"
    ],
    "a": 3,
    "e": "Category 3 forbids flight over open-air assemblies; it is limited to closed or restricted-access sites, or brief transiting.",
    "b": "Regulations"
  },
  {
    "s": "Over People",
    "acs": "UA.I.B",
    "q": "A Category 1 small UAS flown over people must weigh 0.55 lb or less and have:",
    "c": [
      "a second operator present",
      "no exposed parts that could lacerate skin",
      "a metal cage around it",
      "a parachute that stays fully deployed at all times"
    ],
    "a": 1,
    "e": "Category 1 requires the aircraft to be under 0.55 lb with no exposed rotating parts capable of lacerating skin.",
    "b": "Regulations"
  },
  {
    "s": "Over People",
    "acs": "UA.I.B",
    "q": "Category 4 operations over people require the aircraft to have:",
    "c": [
      "a louder motor",
      "two spare batteries",
      "an airworthiness certificate",
      "a bright reflective paint scheme"
    ],
    "a": 2,
    "e": "Category 4 aircraft must hold an airworthiness certificate and be maintained and operated within its limitations.",
    "b": "Regulations"
  },
  {
    "s": "Over People",
    "acs": "UA.I.B",
    "q": "Briefly flying across above scattered people, without hovering over them, is called:",
    "c": [
      "a waiver operation",
      "sustained flight",
      "an open-air assembly",
      "transiting"
    ],
    "a": 3,
    "e": "Transiting is a brief pass over people; sustained flight means remaining over them, which triggers stricter category rules.",
    "b": "Regulations"
  },
  {
    "s": "Over Vehicles",
    "acs": "UA.I.B",
    "q": "Sustained flight over a moving vehicle with people inside is generally allowed only:",
    "c": [
      "in a restricted-access area or by waiver",
      "over highways at night",
      "only if the vehicle is parked briefly first",
      "anywhere below 400 ft"
    ],
    "a": 0,
    "e": "Sustained flight over people in moving vehicles needs a restricted-access area or an approved category or waiver; brief transiting is treated differently.",
    "b": "Regulations"
  },
  {
    "s": "Carriage of Property",
    "acs": "UA.I.B",
    "q": "When carrying property for compensation under Part 107, the aircraft plus its payload must weigh:",
    "c": [
      "under 100 lb total",
      "less than 250 grams only",
      "less than 55 lb total",
      "exactly 55 lb"
    ],
    "a": 2,
    "e": "The combined weight of the aircraft and its cargo must stay under 55 lb, and no hazardous materials may be carried.",
    "b": "Regulations"
  },
  {
    "s": "Carriage of Property",
    "acs": "UA.I.B",
    "q": "Carrying another person's property for hire under Part 107 must be conducted:",
    "c": [
      "within the bounds of a single state",
      "across at least two neighboring states",
      "only over water",
      "only at night"
    ],
    "a": 0,
    "e": "Such carriage must remain intrastate (within one state's boundaries) and follow all other Part 107 rules.",
    "b": "Regulations"
  },
  {
    "s": "Certificate Application",
    "acs": "UA.I.A",
    "q": "After passing the knowledge test and vetting, an applicant first receives a:",
    "c": [
      "temporary certificate valid 120 days",
      "one-flight-only permit",
      "lifetime medical card",
      "permanent plastic card issued instantly"
    ],
    "a": 0,
    "e": "A temporary remote pilot certificate is issued (valid 120 days) while the permanent certificate is processed and mailed.",
    "b": "Regulations"
  },
  {
    "s": "Certificate Application",
    "acs": "UA.I.A",
    "q": "The permanent remote pilot certificate is issued:",
    "c": [
      "by mail after security vetting",
      "at the test center on the spot",
      "only after 100 flights",
      "by the drone's seller"
    ],
    "a": 0,
    "e": "The FAA mails the permanent certificate after the TSA security background check is complete.",
    "b": "Regulations"
  },
  {
    "s": "Currency",
    "acs": "UA.I.A",
    "q": "Compared with the initial test, the required recurrent training is:",
    "c": [
      "a paid retake at a center",
      "longer and in person",
      "a supervised flight test",
      "free and taken online"
    ],
    "a": 3,
    "e": "Recurrent training is a free online course taken every 24 calendar months, unlike the in-person, proctored initial test.",
    "b": "Regulations"
  },
  {
    "s": "Emergency Deviation",
    "acs": "UA.I.B",
    "q": "During an in-flight emergency that requires immediate action, the remote PIC may:",
    "c": [
      "never depart from any rule",
      "hand the controls over to any bystander",
      "only descend, nothing else",
      "deviate from Part 107 as far as needed"
    ],
    "a": 3,
    "e": "Under 107.21 the remote PIC may deviate from any Part 107 rule to the extent necessary to meet an in-flight emergency.",
    "b": "Regulations"
  },
  {
    "s": "Emergency Deviation",
    "acs": "UA.I.B",
    "q": "After deviating from the rules for an emergency, the remote PIC must, if the FAA asks:",
    "c": [
      "surrender the certificate",
      "send a written report of the deviation",
      "immediately ground the drone for a whole year",
      "pay an automatic fine"
    ],
    "a": 1,
    "e": "If the Administrator requests it, the pilot must submit a written report explaining the emergency deviation.",
    "b": "Regulations"
  },
  {
    "s": "Documents",
    "acs": "UA.I.A",
    "q": "On request during an operation, the remote PIC must present the certificate and:",
    "c": [
      "make the aircraft available for inspection",
      "pay an inspection fee",
      "show a pilot logbook only",
      "provide the original dated sales receipt too"
    ],
    "a": 0,
    "e": "The pilot must present the certificate and identification and make the aircraft available to the FAA for inspection or testing.",
    "b": "Regulations"
  },
  {
    "s": "Drug and Alcohol",
    "acs": "UA.I.A",
    "q": "Refusing to submit to an FAA-requested test for drugs or alcohol can result in:",
    "c": [
      "only a brief informal spoken verbal warning",
      "denial or suspension of the certificate",
      "an automatic waiver",
      "a longer flight time"
    ],
    "a": 1,
    "e": "Refusal to take a required drug or alcohol test is grounds for denying an application or suspending the certificate.",
    "b": "Regulations"
  },
  {
    "s": "Applicability",
    "acs": "UA.I.B",
    "q": "Part 107 does NOT apply to:",
    "c": [
      "amateur rockets and moored balloons",
      "aerial photos for pay",
      "survey drones over farms",
      "routine commercial aerial mapping flights"
    ],
    "a": 0,
    "e": "Part 107 excludes amateur rockets, moored balloons and kites, air-carrier operations, and model aircraft flown under Section 44809.",
    "b": "Regulations"
  },
  {
    "s": "Definitions",
    "acs": "UA.I.B",
    "q": "A small unmanned aircraft is defined as one weighing:",
    "c": [
      "less than 55 lb",
      "more than 55 lb",
      "less than 5 lb",
      "less than 250 lb"
    ],
    "a": 0,
    "e": "A small unmanned aircraft weighs less than 55 lb, including everything on board at take-off.",
    "b": "Regulations"
  },
  {
    "s": "Waivers",
    "acs": "UA.I.D",
    "q": "Which of these Part 107 rules may be waived?",
    "c": [
      "operating over people",
      "the careless-operation ban",
      "the Remote ID rule",
      "the registration rule"
    ],
    "a": 0,
    "e": "Operating over people (and rules like visual line of sight and night) can be waived; registration, Remote ID, and careless operation cannot.",
    "b": "Regulations"
  },
  {
    "s": "Waivers",
    "acs": "UA.I.D",
    "q": "A pilot who wants to operate two drones at once would need a waiver of the rule requiring:",
    "c": [
      "a visual observer",
      "daylight-only flight operations",
      "a written checklist",
      "one aircraft per remote pilot"
    ],
    "a": 3,
    "e": "Part 107 limits a remote pilot to one aircraft at a time, so simultaneous multi-aircraft operations require a waiver.",
    "b": "Regulations"
  },
  {
    "s": "Recreational Exception",
    "acs": "UA.I.A",
    "q": "A recreational flyer under Section 44809 must fly within the safety guidelines of:",
    "c": [
      "any random online drone discussion forum group",
      "the drone's warranty card",
      "a recognized community-based organization",
      "the local police department"
    ],
    "a": 2,
    "e": "Recreational flyers must operate within the safety guidelines of an FAA-recognized community-based organization.",
    "b": "Regulations"
  },
  {
    "s": "Recreational Exception",
    "acs": "UA.I.A",
    "q": "To fly recreationally in controlled airspace under 44809, the flyer must:",
    "c": [
      "get authorization, such as through LAANC",
      "call the airport by phone",
      "avoid it only on weekends",
      "simply stay under 400 ft for the whole flight"
    ],
    "a": 0,
    "e": "Recreational flights in controlled airspace still require prior authorization, commonly obtained through LAANC.",
    "b": "Regulations"
  },
  {
    "s": "Supervision",
    "acs": "UA.I.A",
    "q": "A person without a remote pilot certificate may fly a Part 107 operation only if:",
    "c": [
      "they have read the entire manual once through",
      "they fly below 100 ft",
      "a certificated remote PIC supervises",
      "they are over age 21"
    ],
    "a": 2,
    "e": "An uncertificated person may manipulate the controls only under the direct supervision of a certificated remote PIC who can take over.",
    "b": "Regulations"
  },
  {
    "s": "Hazardous Materials",
    "acs": "UA.I.B",
    "q": "Under Part 107, carrying hazardous materials as cargo is:",
    "c": [
      "allowed intrastate only",
      "allowed under 55 lb",
      "prohibited",
      "allowed with a waiver"
    ],
    "a": 2,
    "e": "Part 107 flatly prohibits the carriage of hazardous materials, regardless of weight or waivers.",
    "b": "Regulations"
  },
  {
    "s": "Battery Care",
    "q": "For long-term storage, a lithium-polymer pack is healthiest kept at roughly:",
    "c": [
      "a half charge, near 3.8V per cell",
      "exactly 1 percent",
      "a full charge, 4.2V per cell, always",
      "fully drained to 0V"
    ],
    "a": 0,
    "e": "LiPo packs last longest stored at about half charge (near 3.8V per cell), not full and not empty.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Battery Care",
    "q": "Leaving a lithium battery fully discharged for a long time will:",
    "c": [
      "balance the cells",
      "recharge them faster",
      "improve capacity",
      "damage the cells"
    ],
    "a": 3,
    "e": "Deep discharge and long storage while empty can permanently damage lithium cells, so store them partly charged.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Battery Care",
    "q": "Balance charging a multi-cell lithium pack is done to:",
    "c": [
      "keep all cells at equal voltage",
      "charge the whole pack much faster",
      "cool the pack down",
      "add extra capacity"
    ],
    "a": 0,
    "e": "Balance charging equalizes the individual cell voltages, which keeps the pack healthy and prevents a weak cell.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Battery Care",
    "q": "A swollen or physically damaged lithium battery should be:",
    "c": [
      "isolated in a fireproof container",
      "charged once more, just to test it out",
      "stored with good packs",
      "flown until fully dead"
    ],
    "a": 0,
    "e": "Damaged or puffed lithium packs are a fire risk and should be isolated in a fireproof container and disposed of properly.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Battery Care",
    "q": "Charging a lithium battery when it is below freezing can:",
    "c": [
      "speed up the whole charge safely",
      "balance the pack",
      "increase its capacity",
      "permanently damage the cells"
    ],
    "a": 3,
    "e": "Charging a lithium pack below freezing harms the cells, so let a cold battery warm up before charging.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Battery Care",
    "q": "A hot battery just landed from a demanding flight should be:",
    "c": [
      "allowed to cool before charging",
      "flown again at once",
      "charged immediately at high rate",
      "submerged in water"
    ],
    "a": 0,
    "e": "Let a hot pack cool to a safe temperature before charging; charging while hot stresses the cells.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Battery Capacity",
    "q": "The capacity of a drone battery is rated in:",
    "c": [
      "lumens",
      "engine horsepower units",
      "decibels",
      "milliamp-hours (mAh)"
    ],
    "a": 3,
    "e": "Battery capacity is given in milliamp-hours (mAh); more mAh means more stored charge and, usually, more flight time.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Battery Capacity",
    "q": "To estimate stored energy, multiply the pack's capacity by its:",
    "c": [
      "voltage, giving watt-hours",
      "its total weight, giving pounds",
      "color, giving watts",
      "age, giving cycles"
    ],
    "a": 0,
    "e": "Capacity (in amp-hours) times voltage gives watt-hours of energy, a useful figure for estimating endurance.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Battery Capacity",
    "q": "Choosing a higher-capacity (more mAh) battery usually means:",
    "c": [
      "no change at all",
      "longer flight and less weight",
      "longer flight but more weight",
      "shorter flight time"
    ],
    "a": 2,
    "e": "A larger-capacity pack stores more energy for longer flights but weighs more, which eats into the gain.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Wind",
    "q": "Because of the wind gradient, wind near launch height is usually:",
    "c": [
      "weaker than the wind higher up",
      "always calm",
      "stronger than the wind aloft",
      "exactly the same at all heights"
    ],
    "a": 0,
    "e": "Surface friction slows the wind near the ground, so expect stronger wind as the aircraft climbs.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Performance",
    "q": "Hovering very close to a wall or in a tight corner can be unstable because of:",
    "c": [
      "colder air",
      "recirculating rotor wash",
      "reduced weight",
      "a much stronger GPS signal"
    ],
    "a": 1,
    "e": "Rotor wash bouncing off nearby surfaces recirculates through the props, disturbing the airflow and the hover.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Payload Drag",
    "q": "Bolting on a large, non-streamlined payload will most affect performance by:",
    "c": [
      "adding drag that cuts speed and range",
      "boosting climb rate",
      "greatly reducing the aircraft's total weight",
      "cooling the motors"
    ],
    "a": 0,
    "e": "A bulky external payload adds aerodynamic drag, lowering top speed and shortening endurance beyond the weight penalty alone.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Performance",
    "q": "Holding sustained full throttle, such as a long hard climb, mainly risks:",
    "c": [
      "overheating the motors and ESCs",
      "extending flight time",
      "adding lift for free",
      "cooling the battery pack down nicely"
    ],
    "a": 0,
    "e": "Prolonged maximum output builds heat in the motors and speed controllers, which can lead to thermal shutdown or damage.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Weight and Balance",
    "q": "A 2 lb payload mounted 6 inches from the reference point produces a moment of:",
    "c": [
      "8 inch-pounds",
      "0.3 inch-pounds",
      "3 inch-pounds",
      "12 inch-pounds"
    ],
    "a": 3,
    "e": "Moment equals weight times arm, so 2 lb times 6 inches is 12 inch-pounds.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Weight and Balance",
    "q": "The center of gravity stays within limits as long as the aircraft's total:",
    "c": [
      "payload is symmetrical only",
      "battery is completely fully charged",
      "weight is under 55 lb only",
      "moment stays within the envelope"
    ],
    "a": 3,
    "e": "Balance depends on the total moment; if it falls within the manufacturer's envelope, the CG is within limits.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Center of Gravity",
    "q": "Adding a camera on the nose of a multirotor shifts the center of gravity:",
    "c": [
      "not at all",
      "forward",
      "aft",
      "straight up"
    ],
    "a": 1,
    "e": "A nose-mounted camera moves the CG forward, which the aircraft offsets by tilting and working some motors harder.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Pressure Altitude",
    "q": "Pressure altitude is the altitude shown when the altimeter is set to:",
    "c": [
      "29.92 inches of mercury",
      "the local altimeter setting",
      "the field elevation",
      "zero feet"
    ],
    "a": 0,
    "e": "Pressure altitude is read with the altimeter set to the standard datum of 29.92 inches of mercury.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Pressure Altitude",
    "q": "On a standard day at sea level, pressure altitude is about:",
    "c": [
      "impossible to know",
      "equal to the field elevation",
      "below sea level",
      "roughly 10,000 ft higher than that"
    ],
    "a": 1,
    "e": "Under standard conditions, pressure altitude closely matches true or field elevation.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Density Altitude",
    "q": "On a hot day, density altitude compared with pressure altitude is:",
    "c": [
      "lower",
      "higher",
      "exactly equal",
      "always zero"
    ],
    "a": 1,
    "e": "Heat thins the air, so density altitude rises above pressure altitude, worsening performance.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Battery Care",
    "q": "For transport and storage, lithium packs are safest carried at:",
    "c": [
      "any charge, it is irrelevant",
      "a full charge always",
      "a partial storage charge",
      "completely empty"
    ],
    "a": 2,
    "e": "Carrying and storing lithium packs at a partial storage charge lowers the fire risk and preserves cell health.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Battery Health",
    "q": "A single weak or unbalanced cell in a pack can cause:",
    "c": [
      "a sudden mid-flight power drop",
      "cooler operation",
      "noticeably longer overall flight times",
      "stronger GPS lock"
    ],
    "a": 0,
    "e": "An unbalanced or failing cell can sag hard under load and cause an abrupt loss of power, so balance and inspect packs.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Performance",
    "q": "As air density falls, a fixed-pitch propeller at the same RPM produces:",
    "c": [
      "negative thrust",
      "the same thrust",
      "less thrust",
      "more thrust"
    ],
    "a": 2,
    "e": "Thinner air gives the propeller less to push against, so thrust drops at a given RPM as density falls.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Maneuverability",
    "q": "A heavier drone changing direction quickly will:",
    "c": [
      "become more agile",
      "need less power",
      "carry more momentum and turn wider",
      "stop almost instantly on a dime every time"
    ],
    "a": 2,
    "e": "Greater mass means more momentum, so a heavy drone turns and stops less sharply and needs earlier inputs.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "Preflight",
    "q": "Before charging, a lithium pack should always be:",
    "c": [
      "shaken to mix cells",
      "inspected for swelling or damage",
      "fully drained down to zero volts first",
      "warmed in an oven"
    ],
    "a": 1,
    "e": "Inspect each pack for puffing, dents, or damage before charging; a compromised pack can ignite while charging.",
    "acs": "UA.IV.A",
    "b": "Loading"
  },
  {
    "s": "ADIZ",
    "acs": "UA.II.A",
    "q": "An Air Defense Identification Zone (ADIZ), usually near borders or coasts, is an area where aircraft must:",
    "c": [
      "ignore all NOTAMs",
      "exceed 400 ft AGL",
      "fly only during the late nighttime hours",
      "be identified for national security"
    ],
    "a": 3,
    "e": "An ADIZ requires aircraft to be readily identified in the interest of national security, typically along coastlines and borders.",
    "b": "Airspace"
  },
  {
    "s": "ADS-B",
    "acs": "UA.II.A",
    "q": "Regarding ADS-B Out, a small drone under Part 107 is:",
    "c": [
      "strictly required to broadcast it at all times",
      "required to carry radar",
      "generally not required to broadcast it",
      "banned from any radio use"
    ],
    "a": 2,
    "e": "Drones are generally not required to have ADS-B Out and are discouraged from equipping it, to avoid cluttering the system.",
    "b": "Airspace"
  },
  {
    "s": "NOTAM",
    "acs": "UA.II.A",
    "q": "An FDC NOTAM most often carries:",
    "c": [
      "runway paint colors",
      "pilot birthdays",
      "the local coffee-shop daily opening hours",
      "regulatory information such as TFRs"
    ],
    "a": 3,
    "e": "Flight Data Center (FDC) NOTAMs contain regulatory information, including temporary flight restrictions and chart amendments.",
    "b": "Airspace"
  },
  {
    "s": "NOTAM",
    "acs": "UA.II.A",
    "q": "Compared with a local NOTAM, a distant (D) NOTAM covers information that is:",
    "c": [
      "distributed beyond the local area",
      "never relevant to drones",
      "meant strictly for the tower staff only",
      "hidden from the public"
    ],
    "a": 0,
    "e": "Distant NOTAMs are distributed widely beyond the immediate area, unlike purely local notices.",
    "b": "Airspace"
  },
  {
    "s": "TFR",
    "acs": "UA.II.A",
    "q": "A temporary flight restriction may also be issued around:",
    "c": [
      "all farmland",
      "any parking lot",
      "every single public city park",
      "a space launch or reentry"
    ],
    "a": 3,
    "e": "Space launch and reentry operations can trigger a TFR, along with disasters, hazards, sporting events, and VIP movements.",
    "b": "Airspace"
  },
  {
    "s": "Mode C Veil",
    "acs": "UA.II.A",
    "q": "The Mode C veil is a 30 NM ring around a busy Class B airport where manned aircraft generally need a:",
    "c": [
      "weather radar",
      "parachute",
      "transponder",
      "second engine"
    ],
    "a": 2,
    "e": "Within the 30 NM Mode C veil, manned aircraft need an operating transponder; it is a manned-aircraft rule, not a drone rule.",
    "b": "Airspace"
  },
  {
    "s": "Special Flight Rules",
    "acs": "UA.II.A",
    "q": "The DC Flight Restricted Zone (FRZ), inside the Washington SFRA, is an area where drone flight is:",
    "c": [
      "limited to night hours",
      "prohibited without special approval",
      "freely allowed anywhere below 400 ft",
      "open only on weekends"
    ],
    "a": 1,
    "e": "The DC FRZ is highly restricted; drone operations there require special authorization and are otherwise effectively banned.",
    "b": "Airspace"
  },
  {
    "s": "Class A",
    "acs": "UA.II.A",
    "q": "Class A airspace runs from 18,000 ft MSL up to:",
    "c": [
      "FL600 (about 60,000 ft)",
      "the surface",
      "10,000 ft",
      "only about 20,000 ft up there"
    ],
    "a": 0,
    "e": "Class A extends from 18,000 ft MSL to FL600; it is IFR-only, so a Part 107 drone never operates there.",
    "b": "Airspace"
  },
  {
    "s": "Class E",
    "acs": "UA.II.A",
    "q": "Where not otherwise designated, Class E airspace begins by default at:",
    "c": [
      "60,000 ft MSL",
      "400 ft AGL",
      "14,500 ft MSL",
      "the surface everywhere"
    ],
    "a": 2,
    "e": "Absent a lower floor shown on the chart, Class E starts at 14,500 ft MSL across much of the country.",
    "b": "Airspace"
  },
  {
    "s": "Class B",
    "acs": "UA.II.A",
    "q": "The layered, tiered shape of Class B airspace is often described as:",
    "c": [
      "a single wide flat ring shape",
      "a tall thin tower",
      "a flat pancake",
      "an upside-down wedding cake"
    ],
    "a": 3,
    "e": "Class B is built from stacked shelves that widen with altitude, resembling an upside-down wedding cake.",
    "b": "Airspace"
  },
  {
    "s": "Class C",
    "acs": "UA.II.A",
    "q": "A typical Class C surface core has a radius of about:",
    "c": [
      "50 nautical miles",
      "20 nautical miles",
      "5 nautical miles",
      "1 nautical mile"
    ],
    "a": 2,
    "e": "Class C usually has a 5 NM surface core and a 10 NM shelf, up to about 4,000 ft above the airport.",
    "b": "Airspace"
  },
  {
    "s": "Class D",
    "acs": "UA.II.A",
    "q": "Class D airspace around a towered airport typically has a radius of about:",
    "c": [
      "15 nautical miles",
      "4 nautical miles",
      "40 nautical miles",
      "half a nautical mile"
    ],
    "a": 1,
    "e": "Class D is usually a single circle of roughly 4 NM around a towered field, up to about 2,500 ft above it.",
    "b": "Airspace"
  },
  {
    "s": "Alert Area",
    "acs": "UA.II.A",
    "q": "Flying near a charted Alert Area, a pilot should expect:",
    "c": [
      "guaranteed calm air",
      "absolutely no other aircraft ever",
      "a high volume of pilot training",
      "a total flight ban"
    ],
    "a": 2,
    "e": "Alert Areas warn of a high volume of pilot training or unusual activity; no clearance is needed, but stay vigilant.",
    "b": "Airspace"
  },
  {
    "s": "TFR",
    "acs": "UA.II.A",
    "q": "A hazard or disaster TFR (under 91.137) is meant to:",
    "c": [
      "open the whole area up to all flights",
      "keep aircraft clear of the incident",
      "speed up news coverage",
      "cancel nearby NOTAMs"
    ],
    "a": 1,
    "e": "These TFRs protect responders and aircraft by keeping traffic away from disasters, hazards, and relief operations.",
    "b": "Airspace"
  },
  {
    "s": "TFR",
    "acs": "UA.II.A",
    "q": "Current temporary flight restrictions are best checked at:",
    "c": [
      "a road-traffic map",
      "a live weather radar loop image only",
      "tfr.faa.gov or a NOTAM briefing",
      "last month's chart"
    ],
    "a": 2,
    "e": "Active TFRs are published as NOTAMs and shown at tfr.faa.gov and in apps like B4UFLY; always check before flying.",
    "b": "Airspace"
  },
  {
    "s": "Special Use",
    "acs": "UA.II.A",
    "q": "Which of these is a type of special use airspace?",
    "c": [
      "a Military Operations Area",
      "a Victor airway",
      "a runway apron",
      "a standard traffic pattern leg"
    ],
    "a": 0,
    "e": "Special use airspace includes MOAs, restricted, prohibited, warning, alert areas, controlled firing areas, and NSAs.",
    "b": "Airspace"
  },
  {
    "s": "Prohibited Area",
    "acs": "UA.II.A",
    "q": "P-56, near the U.S. Capitol and White House, is an example of:",
    "c": [
      "an alert area",
      "a warning area",
      "a charted Victor airway",
      "a prohibited area"
    ],
    "a": 3,
    "e": "Prohibited areas like P-56 ban flight entirely for security; they differ from restricted areas, which vary with activity.",
    "b": "Airspace"
  },
  {
    "s": "LAANC",
    "acs": "UA.II.A",
    "q": "LAANC gives near-instant authorization at participating airports, but at fields it does not cover you must:",
    "c": [
      "stay below 50 ft",
      "use a manual FAA DroneZone request",
      "only fly at night",
      "fly without any authorization at all"
    ],
    "a": 1,
    "e": "Where LAANC is unavailable, request authorization manually through the FAA DroneZone portal, which takes longer.",
    "b": "Airspace"
  },
  {
    "s": "UAS Facility Map",
    "acs": "UA.II.A",
    "q": "A UAS Facility Map grid value of 0 for an area means LAANC will:",
    "c": [
      "approve only at night",
      "not auto-approve any altitude there",
      "approve exactly 400 ft",
      "approve any altitude at all instantly"
    ],
    "a": 1,
    "e": "A grid value of 0 means no automatic LAANC approval is available there, so a manual authorization request is needed.",
    "b": "Airspace"
  },
  {
    "s": "Controlled Airspace",
    "acs": "UA.II.A",
    "q": "The classes of controlled airspace are:",
    "c": [
      "A, B, C, D, and E",
      "only Class B and Class C",
      "F and G",
      "only D"
    ],
    "a": 0,
    "e": "Controlled airspace comprises Classes A, B, C, D, and E; Class G is uncontrolled.",
    "b": "Airspace"
  },
  {
    "s": "Victor Airways",
    "acs": "UA.II.B",
    "q": "Victor airways charted in blue on a sectional are actually a form of:",
    "c": [
      "Class A airspace",
      "Class E airspace",
      "restricted airspace",
      "Class B airspace"
    ],
    "a": 1,
    "e": "Victor airways are low-altitude Class E routes defined by VOR radials, drawn as blue lines on the sectional.",
    "b": "Airspace"
  },
  {
    "s": "National Security Area",
    "acs": "UA.II.A",
    "q": "Over a charted National Security Area, pilots are asked to:",
    "c": [
      "climb above 400 ft",
      "voluntarily avoid flying",
      "land the aircraft immediately",
      "broadcast on 121.5"
    ],
    "a": 1,
    "e": "A National Security Area requests voluntary avoidance; flight can be temporarily prohibited by NOTAM when needed.",
    "b": "Airspace"
  },
  {
    "s": "Warning Area",
    "acs": "UA.II.A",
    "q": "A Warning Area differs from a Restricted Area mainly in that it lies:",
    "c": [
      "directly over busy city centers",
      "inside Class D",
      "along every highway",
      "over international waters"
    ],
    "a": 3,
    "e": "Warning Areas sit over international waters beyond 3 NM offshore, so the U.S. cannot designate them as restricted.",
    "b": "Airspace"
  },
  {
    "s": "Class G",
    "acs": "UA.II.A",
    "q": "Most Part 107 flights away from airports take place in which airspace?",
    "c": [
      "Class B",
      "Class A",
      "Class G",
      "Class R"
    ],
    "a": 2,
    "e": "Below the Class E floor and away from airports, operations are in uncontrolled Class G, needing no ATC authorization.",
    "b": "Airspace"
  }
]'''
TEMPLATES_JSON = r'''{"mocks.html": "{% extends \"base.html\" %}\n{% block body %}\n<div class=\"meta\"><span class=\"l\">🎯 Mock exams</span><span class=\"r\">{{ mocks|length }} tests</span></div>\n\n<p style=\"color:var(--muted);font-size:14px;margin:2px 0 14px\">\nFive full-length practice tests, each {{ exam_n }} questions ({{ exam_scored }} scored plus {{ exam_n - exam_scored }} unscored),\n{{ exam_min }} minutes, {{ exam_pass }}% to pass. Weighted to the FAA ACS topics like the real exam. Each mock is a fixed,\ndistinct set you can retake, and a live timer counts down just like the testing center.</p>\n\n{% for mk in mocks %}\n<a class=\"actioncard\" href=\"{{ url_for('mock_start', mid=mk.id) }}\"\n   onclick=\"return confirm('Start {{ mk.title }}? The {{ exam_min }}-minute timer begins now.')\"\n   style=\"margin-bottom:8px\">\n  <b><span class=\"ic\">📝</span>{{ mk.title }}</b>\n  <span>{% if mk.best is not none %}Best score {{ mk.best }}%\n    <span class=\"badge {{ 'pass' if mk.passed else 'fail' }}\" style=\"font-size:11px;padding:1px 7px;margin-left:4px\">{{ 'PASS' if mk.passed else 'RETRY' }}</span>\n    &middot; tap to retake{% else %}Not attempted yet &middot; tap to start{% endif %}</span>\n</a>\n{% endfor %}\n\n<div class=\"btn-row\" style=\"margin-top:14px\"><a class=\"btn\" href=\"{{ url_for('home') }}\">🏠 Home</a></div>\n{% endblock %}\n", "exam.html": "{% extends \"base.html\" %}\n{% block body %}\n<div class=\"meta\">\n  <span class=\"l\">📝 Exam &middot; question {{ n + 1 }} of {{ total }}</span>\n  <span class=\"r timer {{ 'low' if remaining < 300 }}\" id=\"exam-timer\" data-remaining=\"{{ remaining }}\"><span class=\"te\">{{ '⚠️' if remaining < 300 else '⏱️' }}</span><span id=\"exam-timer-text\">{{ remaining_mmss }} left</span></span>\n</div>\n\n<form method=\"post\" action=\"{{ url_for('exam_nav') }}\" id=\"exam-form\">\n  <input type=\"hidden\" name=\"_csrf\" value=\"{{ csrf_token }}\">\n  <input type=\"hidden\" name=\"n\" value=\"{{ n }}\">\n  {% if q.fig %}<div class=\"figbox\">{{ figures[q.fig]|safe }}</div>{% endif %}<div class=\"qcard\"><p class=\"qtext\">{{ q.q_html|safe }}</p></div>\n  <div class=\"choices\">\n    {% for c in choices %}\n    <label class=\"choice\">\n      <input type=\"radio\" name=\"choice\" value=\"{{ c.idx }}\" {{ 'checked' if c.idx == saved }}>\n      <span class=\"cl\">{{ c.letter }}</span><span>{{ c.text }}</span>\n    </label>\n    {% endfor %}\n  </div>\n\n  <div class=\"btn-row\" style=\"margin-bottom:6px\">\n    {% if n > 0 %}<button type=\"submit\" name=\"goto\" value=\"{{ n - 1 }}\">Previous</button>{% endif %}\n    {% if n < total - 1 %}<button type=\"submit\" name=\"goto\" value=\"{{ n + 1 }}\" class=\"btn-primary\" style=\"width:auto;flex:1\">Save and next</button>\n    {% else %}<button type=\"submit\" name=\"finish\" value=\"1\" class=\"btn-primary\" style=\"width:auto;flex:1\">Finish exam</button>{% endif %}\n  </div>\n\n  <div class=\"section-title\">🧭 Question palette</div>\n  <div class=\"palette\">\n    {% for i in range(total) %}\n    <button type=\"submit\" name=\"goto\" value=\"{{ i }}\" class=\"{{ 'answered' if i in answered_set }} {{ 'current' if i == n }}\">{{ i + 1 }}</button>\n    {% endfor %}\n  </div>\n\n  <button type=\"submit\" name=\"finish\" value=\"1\">Finish and grade now</button>\n</form>\n\n<script>\n/* Live exam countdown. Presentation only: the server independently enforces the\n   time limit (exam_q redirects to grading once time is up), so the exam still\n   works and stays enforced with JavaScript disabled. */\n(function(){\n  var el=document.getElementById('exam-timer'),\n      txt=document.getElementById('exam-timer-text'),\n      form=document.getElementById('exam-form');\n  if(!el||!txt||!form) return;\n  var left=parseInt(el.getAttribute('data-remaining'),10)||0, done=false;\n  function pad(n){return (n<10?'0':'')+n;}\n  function tick(){\n    if(done) return;\n    if(left<=0){\n      done=true;\n      var f=document.createElement('input');\n      f.type='hidden'; f.name='finish'; f.value='1';\n      form.appendChild(f); form.submit(); return;\n    }\n    var h=Math.floor(left/3600), m=Math.floor((left%3600)/60), s=left%60;\n    txt.firstChild.nodeValue=(h>0?h+':'+pad(m):''+m)+':'+pad(s)+' left';\n    if(left<300) el.classList.add('low');\n    left--; setTimeout(tick,1000);\n  }\n  tick();\n})();\n</script>\n{% endblock %}\n", "home.html": "{% extends \"base.html\" %}\n{% block body %}\n<div class=\"tiles\">\n  <div class=\"tile\"><span class=\"ic\">🎯</span><b>{{ lifetime_pct if lifetime_pct is not none else \"--\" }}{{ \"%\" if lifetime_pct is not none else \"\" }}</b><span>lifetime accuracy</span></div>\n  <div class=\"tile\"><span class=\"ic\">✍️</span><b>{{ total_answered }}</b><span>questions answered</span></div>\n  <div class=\"tile\"><span class=\"ic\">📚</span><b>{{ to_review }}</b><span>on your study list</span></div>\n</div>\n\n{% if not user %}\n<a class=\"actioncard\" href=\"{{ url_for('register') }}\" style=\"border-color:var(--blue);margin-bottom:8px\">\n  <b><span class=\"ic\">☁️</span>Create an account to sync across devices</b>\n  <span>Your current progress moves into the account automatically. Or <span style=\"text-decoration:underline\">sign in</span> if you have one.</span>\n</a>\n{% endif %}\n\n<div class=\"section-title\">Study</div>\n{% if to_review %}\n<a class=\"hero\" href=\"{{ url_for('drill') }}\"><span class=\"ic\">🎯</span><b>Drill your {{ to_review }} missed question{{ 's' if to_review != 1 }}</b><span>Targeted practice on exactly what you keep getting wrong, hardest first</span></a>\n{% else %}\n<a class=\"hero\" href=\"{{ url_for('practice', bucket='All') }}\"><span class=\"ic\">✍️</span><b>Practice all topics</b><span>Instant feedback and the rule behind every answer</span></a>\n{% endif %}\n<div class=\"cards\">\n  <a class=\"actioncard\" href=\"{{ url_for('learn') }}\"><b><span class=\"ic\">📖</span>Learn the material</b><span>Read through each topic with the answer and rule, no quiz pressure</span></a>\n  <a class=\"actioncard\" href=\"{{ url_for('cheatsheet') }}\"><b><span class=\"ic\">🗒️</span>Rules cheat sheet</b><span>Every key rule by topic, printable for last-minute review</span></a>\n  <a class=\"actioncard\" href=\"{{ url_for('practice', figures=1) }}\"><b><span class=\"ic\">🗺️</span>Chart reading</b><span>Practice the sectional-figure questions on their own</span></a>\n  <a class=\"actioncard\" href=\"{{ url_for('exam_start') }}\"><b><span class=\"ic\">📝</span>Exam simulation</b><span>{{ exam_n }} questions ({{ exam_scored }} scored), {{ exam_min }} min, {{ exam_pass }}% to pass</span></a>\n  <a class=\"actioncard\" href=\"{{ url_for('mocks') }}\"><b><span class=\"ic\">🎯</span>Mock exams (timed)</b><span>Five full {{ exam_n }}-question tests, {{ exam_min }} min each, live timer and scoring like the real exam</span></a>\n  {% if to_review %}\n  <a class=\"actioncard\" href=\"{{ url_for('practice', bucket='All') }}\"><b><span class=\"ic\">✍️</span>Practice all topics</b><span>Instant feedback and the rule behind each answer</span></a>\n  {% endif %}\n  <a class=\"actioncard\" href=\"{{ url_for('focus') }}\"><b><span class=\"ic\">🎚️</span>Focus on weak topics</b><span>Practice weighted toward your lowest-scoring and not-yet-seen topics</span></a>\n  <a class=\"actioncard\" href=\"{{ url_for('review') }}\"><b><span class=\"ic\">📊</span>Study list and stats</b><span>Every missed question, grouped by topic</span></a>\n  <a class=\"actioncard\" href=\"{{ url_for('studysheet') }}\"><b><span class=\"ic\">📄</span>ACS study sheet</b><span>Your weak ACS tasks and the rules to study, printable</span></a>\n</div>\n\n<div class=\"section-title\">Practice by topic</div>\n<div class=\"bgrid\">\n  {% for b in buckets %}\n  <a class=\"bcard\" href=\"{{ url_for('practice', bucket=b.name) }}\">\n    <div class=\"top-row\">\n      <div class=\"n\"><span class=\"ic\">{{ icons[b.name] }}</span>{{ b.name }} ({{ soft_count(b.count) }})</div>\n      {% set m = mastery(b.pct) %}<span class=\"mbadge {{ m.cls }}\">{{ m.emoji }} {{ m.label }}</span>\n    </div>\n    <div class=\"pct\">{{ b.pct if b.pct is not none else \"not started\" }}{{ \"%\" if b.pct is not none else \"\" }}</div>\n    <div class=\"bar\"><i style=\"width:{{ b.pct or 0 }}%;background:{{ b.color }}\"></i></div>\n  </a>\n  {% endfor %}\n</div>\n\n<div class=\"section-title\">Manage</div>\n<div class=\"btn-row\">\n  <a class=\"btn\" href=\"{{ url_for('export_progress') }}\">📤 Export progress</a>\n  <form method=\"post\" action=\"{{ url_for('reset_progress') }}\" onsubmit=\"return confirm('Erase all saved progress on this server for your browser?')\" style=\"display:inline\">\n    <input type=\"hidden\" name=\"_csrf\" value=\"{{ csrf_token }}\">\n    <button type=\"submit\">🗑️ Reset all</button>\n  </form>\n</div>\n{% endblock %}\n", "learn.html": "{% extends \"base.html\" %}\n{% block title %}Learn - Part 107 Ground School{% endblock %}\n{% block body %}\n<div class=\"section-title\">📖 Learn by topic</div>\n<div class=\"filters\">\n  {% for b in bucket_names %}\n  <a href=\"{{ url_for('learn', bucket=b, n=0) }}\" class=\"{{ 'active' if bucket == b }}\"><span class=\"ic\">{{ icons[b] }}</span>{{ b }}</a>\n  {% endfor %}\n</div>\n\n<div class=\"meta\">\n  <span class=\"l\">{{ icons[bucket] }} {{ bucket }}</span>\n  <span class=\"r\">card {{ n + 1 }} of {{ total }}</span>\n</div>\n\n{% if q.fig %}<div class=\"figbox\">{{ figures[q.fig]|safe }}</div>{% endif %}<div class=\"qcard\"><p class=\"qtext\">{{ q.q_html|safe }}</p></div>\n<div class=\"choices\">\n  {% for c in choices %}\n  <div class=\"choice {{ 'correct' if c.idx == q.a else 'dim' }}\">\n    <span class=\"cl\">{{ c.letter }}</span><span>{{ c.text }}</span>\n    {% if c.idx == q.a %}<span class=\"status\">✅</span>{% endif %}\n  </div>\n  {% endfor %}\n</div>\n<div class=\"explain ok\"><span class=\"rl\">📌 the rule</span>{{ q.e }}</div>\n\n<div class=\"btn-row\">\n  {% if n > 0 %}<a class=\"btn\" href=\"{{ url_for('learn', bucket=bucket, n=n-1) }}\">← Previous</a>{% endif %}\n  {% if n < total - 1 %}\n  <a class=\"btn-primary\" href=\"{{ url_for('learn', bucket=bucket, n=n+1) }}\" style=\"width:auto;flex:1\">Next card →</a>\n  {% else %}\n  <a class=\"btn-primary\" href=\"{{ url_for('practice', bucket=bucket) }}\" style=\"width:auto;flex:1\">✍️ Quiz this topic →</a>\n  {% endif %}\n</div>\n<div class=\"center\" style=\"margin-top:12px\"><a href=\"{{ url_for('home') }}\" style=\"font-size:13px;color:var(--muted)\">Back to home</a></div>\n{% endblock %}\n", "review.html": "{% extends \"base.html\" %}\n{% block body %}\n<div class=\"section-title\">📈 Lifetime accuracy by topic</div>\n{% if lifetime %}\n{% for b in lifetime %}\n<div class=\"bdrow\">\n  <span class=\"nm\"><span class=\"ic\">{{ icons[b.name] }}</span>{{ b.name }}</span>\n  <span class=\"tr bar\"><i style=\"width:{{ b.pct }}%;background:{{ b.color }}\"></i></span>\n  <span class=\"vl\" style=\"color:{{ b.color }}\">{{ b.c }}/{{ b.n }} ({{ b.pct }}%)</span>\n</div>\n{% endfor %}\n{% else %}\n<div class=\"empty\">📭 No answers logged yet. Start practicing from the home page.</div>\n{% endif %}\n\n<div class=\"section-title\">📚 Study list, every missed question</div>\n<div class=\"filters\">\n  <a href=\"{{ url_for('review') }}\" class=\"{{ 'active' if not active_bucket }}\">All</a>\n  {% for b in bucket_names %}\n  <a href=\"{{ url_for('review', bucket=b) }}\" class=\"{{ 'active' if active_bucket == b }}\"><span class=\"ic\">{{ icons[b] }}</span>{{ b }}</a>\n  {% endfor %}\n</div>\n\n{% if acs_summary %}\n<div class=\"acssummary\">\n  <div class=\"acssummary-h\">FAA ACS tasks to study{{ ' (this topic)' if active_bucket }}</div>\n  {% for a in acs_summary %}\n  <div class=\"acsrow\"><span class=\"acscode\">{{ a.code }}</span><span class=\"acstitle\">{{ a.title }}</span><span class=\"acsn\">{{ a.n }}</span></div>\n  {% endfor %}\n</div>\n{% endif %}\n\n{% if missed %}\n<div class=\"btn-row\" style=\"margin-bottom:14px\">\n  <a class=\"btn-primary\" href=\"{{ url_for('drill', bucket=active_bucket) }}\" style=\"width:auto;flex:1\">🎯 Drill {{ 'these' if active_bucket else 'all' }} missed questions</a>\n  <a class=\"btn\" href=\"{{ url_for('studysheet') }}\">📄 ACS study sheet</a>\n</div>\n{% endif %}\n\n{% if missed %}\n{% for grp in missed %}\n<div class=\"mbucket\">\n  <div class=\"mbname\"><span class=\"ic\">{{ icons[grp.name] }}</span>{{ grp.name }} <span class=\"countbadge\">{{ grp.qs|length }} to review</span></div>\n  {% for m in grp.qs %}\n  <div class=\"mcard\">\n    <div class=\"mq\">{{ m.q_html|safe }}{% if m.misses > 1 %} <span style=\"color:var(--red);font-family:var(--mono);font-size:11px\">🔁 missed {{ m.misses }}x</span>{% endif %}</div>\n    <div class=\"ma\">✅ {{ m.letter }}. {{ m.answer }}</div>\n    <div class=\"mr\">{{ m.e }}</div>\n    {% if m.acs %}<div class=\"macs\">ACS <span class=\"acs\" title=\"{{ acs_tasks[m.acs] }}\">{{ m.acs }}</span> &middot; {{ acs_tasks[m.acs] }}</div>{% endif %}\n  </div>\n  {% endfor %}\n</div>\n{% endfor %}\n{% else %}\n<div class=\"empty\">🎉 Nothing on your study list{{ ' for this topic' if active_bucket }}. Miss a question and it lands here.</div>\n{% endif %}\n{% endblock %}\n", "login.html": "{% extends \"base.html\" %}\n{% block title %}Sign in - Part 107 Ground School{% endblock %}\n{% block body %}\n<div class=\"section-title\">Sign in</div>\n{% if error %}<div class=\"explain bad\" style=\"margin-bottom:14px\">{{ error }}</div>{% endif %}\n<form method=\"post\" action=\"{{ url_for('login') }}\" class=\"qcard\">\n  <input type=\"hidden\" name=\"_csrf\" value=\"{{ csrf_token }}\">\n  <label class=\"flabel\">Email</label>\n  <input type=\"email\" name=\"email\" value=\"{{ email or '' }}\" autocomplete=\"email\" required\n         class=\"field\" style=\"margin-bottom:14px\" placeholder=\"you@example.com\">\n  <label class=\"flabel\">Password</label>\n  <input type=\"password\" name=\"password\" autocomplete=\"current-password\" required\n         class=\"field\" style=\"margin-bottom:18px\">\n  <button type=\"submit\" class=\"btn-primary\">Sign in</button>\n</form>\n<div class=\"center\" style=\"font-size:14px;color:var(--muted)\">No account yet? <a href=\"{{ url_for('register') }}\">Create one</a></div>\n{% endblock %}\n", "exam_result.html": "{% extends \"base.html\" %}\n{% block body %}\n{% if mock_title %}<div class=\"section-title\" style=\"text-align:center;margin-top:4px\">{{ mock_title }}</div>{% endif %}\n<div class=\"center\" style=\"padding:8px 0 16px\">\n  <div class=\"result-emoji\">{{ '🎉' if passed else '💪' }}</div>\n  <div class=\"bigpct\" style=\"color:{{ pass_color }}\">{{ pct }}%</div>\n  <div style=\"margin:10px 0\"><span class=\"badge {{ 'pass' if passed else 'fail' }}\"><span class=\"be\">{{ '✅' if passed else '❌' }}</span>{{ 'Pass' if passed else 'Did not pass' }}</span></div>\n  <div style=\"font-size:14px;color:var(--muted)\">{{ correct }} of {{ total }} correct &middot; {{ time_used }} used &middot; {{ exam_pass }}% needed</div>\n  {% if experimental %}<div style=\"font-size:12px;color:var(--muted);margin-top:5px\">{{ experimental }} experimental questions were not scored, just like the real exam.</div>{% endif %}\n</div>\n\n<div class=\"btn-row\" style=\"justify-content:center;margin-bottom:8px\">\n  {% if mock_id is not none %}<a class=\"btn\" href=\"{{ url_for('mock_start', mid=mock_id) }}\">🔄 Retake this mock</a><a class=\"btn\" href=\"{{ url_for('mocks') }}\">🎯 All mocks</a>{% else %}<a class=\"btn\" href=\"{{ url_for('exam_start') }}\">🔄 New exam</a>{% endif %}\n  <a class=\"btn\" href=\"{{ url_for('history') }}\">📈 Progress</a>\n  {% if missed %}<a class=\"btn\" href=\"{{ url_for('drill') }}\">🎯 Drill misses</a>{% endif %}\n  <a class=\"btn\" href=\"{{ url_for('review') }}\">📚 Review study list</a>\n  <a class=\"btn\" href=\"{{ url_for('home') }}\">🏠 Home</a>\n</div>\n\n<div class=\"section-title\">📊 By topic</div>\n{% for b in by_bucket %}\n<div class=\"bdrow\">\n  <span class=\"nm\"><span class=\"ic\">{{ icons[b.name] }}</span>{{ b.name }}</span>\n  <span class=\"tr bar\"><i style=\"width:{{ b.pct }}%;background:{{ b.color }}\"></i></span>\n  <span class=\"vl\" style=\"color:{{ b.color }}\">{{ b.c }}/{{ b.n }} ({{ b.pct }}%)</span>\n</div>\n{% endfor %}\n\n{% if acs_summary %}\n<div class=\"section-title\">🎯 FAA ACS tasks to study</div>\n<div class=\"acssummary\">\n  {% for a in acs_summary %}\n  <div class=\"acsrow\"><span class=\"acscode\">{{ a.code }}</span><span class=\"acstitle\">{{ a.title }}</span><span class=\"acsn\">{{ a.n }}</span></div>\n  {% endfor %}\n</div>\n{% endif %}\n\n{% if missed %}\n<div class=\"section-title\">📌 Missed questions and the rule</div>\n{% for grp in missed %}\n<div class=\"mbucket\">\n  <div class=\"mbname\"><span class=\"ic\">{{ icons[grp.name] }}</span>{{ grp.name }} <span class=\"countbadge\">{{ grp.qs|length }} missed</span></div>\n  {% for m in grp.qs %}\n  <div class=\"mcard\">\n    <div class=\"mq\">{{ m.q_html|safe }}</div>\n    <div class=\"ma\">✅ {{ m.letter }}. {{ m.answer }}</div>\n    <div class=\"mr\">{{ m.e }}</div>\n    {% if m.acs %}<div class=\"macs\">ACS <span class=\"acs\" title=\"{{ acs_tasks[m.acs] }}\">{{ m.acs }}</span> &middot; {{ acs_tasks[m.acs] }}</div>{% endif %}\n  </div>\n  {% endfor %}\n</div>\n{% endfor %}\n{% else %}\n<div class=\"empty\">🌟 Perfect run. Nothing missed.</div>\n{% endif %}\n{% endblock %}\n", "cheatsheet.html": "{% extends \"base.html\" %}\n{% block title %}Rules cheat sheet - Part 107 Ground School{% endblock %}\n{% block body %}\n<div class=\"section-title\">🗒️ Rules cheat sheet</div>\n<p class=\"cs-intro\">{{ total }} key rules across all topics. Use your browser's print (Cmd or Ctrl + P) to save or print a clean copy for last-minute review.</p>\n<div class=\"csleg\">\n  <div class=\"csleg-h\" style=\"margin-top:0\">🗺️ Sectional chart symbology</div>\n  <p class=\"csleg-note\">A quick visual key for reading a VFR sectional. The color rule does most of the work: <b>blue</b> marks towered airports and Class B/C/D-with-tower features, while <b>magenta</b> marks non-towered airports, Class C, and Class E that starts at the surface. This is a study aid; the real knowledge test shows excerpts from the FAA testing supplement.</p>\n  <p class=\"csleg-note\"><a href=\"{{ url_for('practice', figures=1) }}\">Practice the chart-reading questions &rarr;</a></p>\n\n  <div class=\"csleg-h\">Airports</div>\n  <div class=\"csleg-grid\">\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><circle cx=\"30\" cy=\"20\" r=\"11\" fill=\"none\" stroke=\"#2E5AAC\" stroke-width=\"2\"/><g stroke=\"#2E5AAC\" stroke-width=\"2.4\" stroke-linecap=\"round\"><line x1=\"21\" y1=\"20\" x2=\"39\" y2=\"20\"/><line x1=\"25\" y1=\"13\" x2=\"35\" y2=\"27\"/></g></svg></div><div class=\"csleg-txt\"><b>Towered airport</b><span>Blue. Has an operating control tower.</span></div></div>\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><circle cx=\"30\" cy=\"20\" r=\"11\" fill=\"none\" stroke=\"#B0327D\" stroke-width=\"2\"/><g stroke=\"#B0327D\" stroke-width=\"2.4\" stroke-linecap=\"round\"><line x1=\"21\" y1=\"20\" x2=\"39\" y2=\"20\"/><line x1=\"25\" y1=\"13\" x2=\"35\" y2=\"27\"/></g></svg></div><div class=\"csleg-txt\"><b>Non-towered airport</b><span>Magenta. No control tower.</span></div></div>\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><circle cx=\"30\" cy=\"20\" r=\"9\" fill=\"none\" stroke=\"#2E5AAC\" stroke-width=\"2\"/><g stroke=\"#2E5AAC\" stroke-width=\"2.2\" stroke-linecap=\"round\"><line x1=\"30\" y1=\"5\" x2=\"30\" y2=\"10\"/><line x1=\"30\" y1=\"30\" x2=\"30\" y2=\"35\"/><line x1=\"15\" y1=\"20\" x2=\"20\" y2=\"20\"/><line x1=\"40\" y1=\"20\" x2=\"45\" y2=\"20\"/></g></svg></div><div class=\"csleg-txt\"><b>Fuel / services</b><span>Tick marks around the circle.</span></div></div>\n  </div>\n\n  <div class=\"csleg-h\">Airspace boundaries</div>\n  <div class=\"csleg-grid\">\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><line x1=\"6\" y1=\"20\" x2=\"54\" y2=\"20\" stroke=\"#2E5AAC\" stroke-width=\"3.6\"/></svg></div><div class=\"csleg-txt\"><b>Class B</b><span>Solid blue line.</span></div></div>\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><line x1=\"6\" y1=\"20\" x2=\"54\" y2=\"20\" stroke=\"#B0327D\" stroke-width=\"3.6\"/></svg></div><div class=\"csleg-txt\"><b>Class C</b><span>Solid magenta line.</span></div></div>\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><line x1=\"6\" y1=\"20\" x2=\"54\" y2=\"20\" stroke=\"#2E5AAC\" stroke-width=\"2.8\" stroke-dasharray=\"7 4\"/></svg></div><div class=\"csleg-txt\"><b>Class D</b><span>Dashed blue line.</span></div></div>\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><line x1=\"6\" y1=\"20\" x2=\"54\" y2=\"20\" stroke=\"#B0327D\" stroke-width=\"2.8\" stroke-dasharray=\"7 4\"/></svg></div><div class=\"csleg-txt\"><b>Class E to surface</b><span>Dashed magenta line.</span></div></div>\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><defs><linearGradient id=\"ge7\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\"><stop offset=\"0\" stop-color=\"#B0327D\" stop-opacity=\".55\"/><stop offset=\"1\" stop-color=\"#B0327D\" stop-opacity=\"0\"/></linearGradient></defs><rect x=\"6\" y=\"13\" width=\"48\" height=\"15\" fill=\"url(#ge7)\"/></svg></div><div class=\"csleg-txt\"><b>Class E at 700 ft AGL</b><span>Soft magenta fade (faded side = lower floor).</span></div></div>\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><defs><linearGradient id=\"ge12\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\"><stop offset=\"0\" stop-color=\"#2E5AAC\" stop-opacity=\".5\"/><stop offset=\"1\" stop-color=\"#2E5AAC\" stop-opacity=\"0\"/></linearGradient></defs><rect x=\"6\" y=\"13\" width=\"48\" height=\"15\" fill=\"url(#ge12)\"/></svg></div><div class=\"csleg-txt\"><b>Class E at 1,200 ft AGL</b><span>Soft blue fade.</span></div></div>\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><line x1=\"6\" y1=\"25\" x2=\"54\" y2=\"25\" stroke=\"#2E5AAC\" stroke-width=\"2.4\"/><g stroke=\"#2E5AAC\" stroke-width=\"2\"><line x1=\"12\" y1=\"25\" x2=\"9\" y2=\"16\"/><line x1=\"23\" y1=\"25\" x2=\"20\" y2=\"16\"/><line x1=\"34\" y1=\"25\" x2=\"31\" y2=\"16\"/><line x1=\"45\" y1=\"25\" x2=\"42\" y2=\"16\"/></g></svg></div><div class=\"csleg-txt\"><b>Prohibited / restricted</b><span>Blue line with hatching inside.</span></div></div>\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><line x1=\"6\" y1=\"25\" x2=\"54\" y2=\"25\" stroke=\"#B0327D\" stroke-width=\"2.4\"/><g stroke=\"#B0327D\" stroke-width=\"2\"><line x1=\"12\" y1=\"25\" x2=\"9\" y2=\"16\"/><line x1=\"23\" y1=\"25\" x2=\"20\" y2=\"16\"/><line x1=\"34\" y1=\"25\" x2=\"31\" y2=\"16\"/><line x1=\"45\" y1=\"25\" x2=\"42\" y2=\"16\"/></g></svg></div><div class=\"csleg-txt\"><b>MOA / alert area</b><span>Magenta line with hatching.</span></div></div>\n  </div>\n\n  <div class=\"csleg-h\">Altitude labels</div>\n  <div class=\"csleg-grid\">\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><g font-family=\"monospace\" font-weight=\"700\" fill=\"#1c2733\" text-anchor=\"middle\"><text x=\"30\" y=\"16\" font-size=\"12\">118</text><text x=\"30\" y=\"34\" font-size=\"12\">40</text></g><line x1=\"16\" y1=\"20\" x2=\"44\" y2=\"20\" stroke=\"#1c2733\" stroke-width=\"1.4\"/></svg></div><div class=\"csleg-txt\"><b>Ceiling over floor</b><span>118/40 = top 11,800, floor 4,000 ft MSL.</span></div></div>\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><g font-family=\"monospace\" font-weight=\"700\" fill=\"#1c2733\" text-anchor=\"middle\"><text x=\"30\" y=\"16\" font-size=\"12\">70</text><text x=\"30\" y=\"34\" font-size=\"11\">SFC</text></g><line x1=\"16\" y1=\"20\" x2=\"44\" y2=\"20\" stroke=\"#1c2733\" stroke-width=\"1.4\"/></svg></div><div class=\"csleg-txt\"><b>Up to surface</b><span>SFC = from the ground up.</span></div></div>\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><text x=\"30\" y=\"25\" font-size=\"15\" font-family=\"monospace\" font-weight=\"700\" fill=\"#B0327D\" text-anchor=\"middle\">700</text></svg></div><div class=\"csleg-txt\"><b>Magenta floor figure</b><span>Class E floor in feet AGL.</span></div></div>\n  </div>\n\n  <div class=\"csleg-h\">Obstacles and terrain</div>\n  <div class=\"csleg-grid\">\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><path d=\"M25 31 L30 9 L35 31\" fill=\"none\" stroke=\"#1c2733\" stroke-width=\"2\"/><circle cx=\"30\" cy=\"31\" r=\"1.7\" fill=\"#1c2733\"/></svg></div><div class=\"csleg-txt\"><b>Single obstacle</b><span>Tower, antenna, or similar.</span></div></div>\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><path d=\"M16 31 L22 13 L28 31\" fill=\"none\" stroke=\"#1c2733\" stroke-width=\"2\"/><path d=\"M30 31 L37 9 L44 31\" fill=\"none\" stroke=\"#1c2733\" stroke-width=\"2\"/></svg></div><div class=\"csleg-txt\"><b>Group obstacle</b><span>Two or more close together.</span></div></div>\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><path d=\"M25 31 L30 11 L35 31\" fill=\"none\" stroke=\"#1c2733\" stroke-width=\"2\"/><circle cx=\"30\" cy=\"31\" r=\"1.7\" fill=\"#1c2733\"/><g stroke=\"#B0327D\" stroke-width=\"1.8\" stroke-linecap=\"round\"><line x1=\"30\" y1=\"11\" x2=\"30\" y2=\"5\"/><line x1=\"25\" y1=\"8\" x2=\"27\" y2=\"11\"/><line x1=\"35\" y1=\"8\" x2=\"33\" y2=\"11\"/></g></svg></div><div class=\"csleg-txt\"><b>Lighted obstacle</b><span>Magenta rays = lighting.</span></div></div>\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><text x=\"30\" y=\"18\" font-size=\"10\" font-family=\"monospace\" font-weight=\"700\" fill=\"#1c2733\" text-anchor=\"middle\">1549</text><text x=\"30\" y=\"32\" font-size=\"10\" font-family=\"monospace\" fill=\"#1c2733\" text-anchor=\"middle\">(549)</text></svg></div><div class=\"csleg-txt\"><b>Obstacle height</b><span>Top MSL, and (AGL) above ground.</span></div></div>\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><text x=\"20\" y=\"29\" font-size=\"20\" font-family=\"monospace\" font-weight=\"700\" fill=\"#5c6672\" text-anchor=\"middle\">2</text><text x=\"38\" y=\"22\" font-size=\"13\" font-family=\"monospace\" font-weight=\"700\" fill=\"#5c6672\" text-anchor=\"middle\">5</text></svg></div><div class=\"csleg-txt\"><b>Max elevation figure</b><span>2 5 = 2,500 ft, highest in that quadrant.</span></div></div>\n  </div>\n\n  <div class=\"csleg-h\">Navigation</div>\n  <div class=\"csleg-grid\">\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><line x1=\"22\" y1=\"7\" x2=\"22\" y2=\"33\" stroke=\"#B0327D\" stroke-width=\"2\"/><path d=\"M22 9 L40 14 L22 19 Z\" fill=\"#B0327D\"/></svg></div><div class=\"csleg-txt\"><b>Visual checkpoint</b><span>Magenta flag at a landmark.</span></div></div>\n    <div class=\"csleg-item\"><div class=\"csleg-sym\"><svg viewBox=\"0 0 60 40\"><line x1=\"6\" y1=\"22\" x2=\"54\" y2=\"22\" stroke=\"#2E5AAC\" stroke-width=\"1.6\"/><text x=\"30\" y=\"15\" font-size=\"9\" font-family=\"monospace\" fill=\"#2E5AAC\" text-anchor=\"middle\">V23</text></svg></div><div class=\"csleg-txt\"><b>Victor airway</b><span>Low-altitude route; expect traffic.</span></div></div>\n  </div>\n</div>\n{% for grp in sheet %}\n<div class=\"cs-group\">\n  <div class=\"cs-head\"><span class=\"ic\">{{ icons[grp.name] }}</span>{{ grp.name }} <span class=\"cs-n\">{{ soft_count(grp.count) }}</span></div>\n  <ul class=\"cs-list\">\n    {% for r in grp.rules %}<li>{{ r }}</li>{% endfor %}\n  </ul>\n</div>\n{% endfor %}\n{% endblock %}\n", "history.html": "{% extends \"base.html\" %}\n{% block title %}Exam readiness - Part 107 Ground School{% endblock %}\n{% block body %}\n<div class=\"section-title\">🎓 Exam readiness</div>\n{% if not taken %}\n<div class=\"empty\">📝 No practice exams logged yet. Take one to see your readiness verdict and score trend.</div>\n<div class=\"center\" style=\"margin-top:10px\"><a class=\"btn-primary\" href=\"{{ url_for('exam_start') }}\" style=\"width:auto;display:inline-block\">Start an exam</a></div>\n{% else %}\n<div class=\"qcard\" style=\"text-align:center\">\n  <span class=\"mbadge {{ verdict.cls }}\" style=\"font-size:12px;padding:5px 12px\">{{ verdict.emoji }} {{ verdict.label }}</span>\n  <p style=\"font-size:14px;color:var(--muted);margin:11px 0 0\">{{ verdict.note }}</p>\n</div>\n\n<div class=\"tiles\">\n  <div class=\"tile\"><span class=\"ic\">🏅</span><b>{{ best }}%</b><span>best score</span></div>\n  <div class=\"tile\"><span class=\"ic\">📊</span><b>{{ avg5 }}%</b><span>recent average</span></div>\n  <div class=\"tile\"><span class=\"ic\">✅</span><b>{{ pass_rate }}%</b><span>pass rate</span></div>\n</div>\n\n<div class=\"section-title\">📈 Score trend &middot; last {{ trend|length }}</div>\n<div class=\"trend\">\n  <div class=\"passline\" style=\"bottom:{{ exam_pass }}%\"><span>{{ exam_pass }}% pass</span></div>\n  {% for s in trend %}\n  <div class=\"tb {{ 'pass' if s.passed else 'fail' }}\" style=\"height:{{ s.pct }}%\" title=\"{{ s.pct }}%\"></div>\n  {% endfor %}\n</div>\n<div class=\"center\" style=\"font-family:var(--mono);font-size:10px;color:var(--muted)\">oldest → newest</div>\n\n<div class=\"section-title\">🗒️ Recent exams</div>\n{% for s in recent %}\n<div class=\"bdrow\">\n  <span class=\"nm\" style=\"width:auto;flex:1\">{{ s.when }}</span>\n  <span class=\"vl\" style=\"width:auto;color:var(--muted)\">{{ s.correct }}/{{ s.total }}</span>\n  <span class=\"vl\" style=\"color:{{ '#1F8A5B' if s.passed else '#C23B3B' }}\">{{ s.pct }}%</span>\n  <span class=\"badge {{ 'pass' if s.passed else 'fail' }}\" style=\"font-size:10px;padding:3px 9px\">{{ '✅' if s.passed else '❌' }} {{ 'Pass' if s.passed else 'Fail' }}</span>\n</div>\n{% endfor %}\n\n<div class=\"btn-row\" style=\"justify-content:center;margin-top:16px\">\n  <a class=\"btn\" href=\"{{ url_for('exam_start') }}\">🔄 New exam</a>\n  <a class=\"btn\" href=\"{{ url_for('home') }}\">🏠 Home</a>\n</div>\n{% endif %}\n{% endblock %}\n", "register.html": "{% extends \"base.html\" %}\n{% block title %}Create account - Part 107 Ground School{% endblock %}\n{% block body %}\n<div class=\"section-title\">Create an account</div>\n<p style=\"font-size:14px;color:var(--muted);margin-bottom:14px\">Sign in with your email so your progress follows you across devices. If you have been practicing already, that progress moves into your account automatically.</p>\n{% if error %}<div class=\"explain bad\" style=\"margin-bottom:14px\">{{ error }}</div>{% endif %}\n<form method=\"post\" action=\"{{ url_for('register') }}\" class=\"qcard\">\n  <input type=\"hidden\" name=\"_csrf\" value=\"{{ csrf_token }}\">\n  <label class=\"flabel\">Email</label>\n  <input type=\"email\" name=\"email\" value=\"{{ email or '' }}\" autocomplete=\"email\" required\n         class=\"field\" style=\"margin-bottom:14px\" placeholder=\"you@example.com\">\n  <label class=\"flabel\">Password (at least 6 characters)</label>\n  <input type=\"password\" name=\"password\" autocomplete=\"new-password\" required\n         class=\"field\" style=\"margin-bottom:18px\">\n  <button type=\"submit\" class=\"btn-primary\">Create account</button>\n</form>\n<div class=\"center\" style=\"font-size:14px;color:var(--muted)\">Already have an account? <a href=\"{{ url_for('login') }}\">Sign in</a></div>\n{% endblock %}\n", "base.html": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n<meta name=\"theme-color\" content=\"{{ '#1E2731' if dark else '#EAEFF3' }}\">\n<title>{% block title %}Part 107 Ground School{% endblock %}</title>\n<link rel=\"icon\" type=\"image/svg+xml\" href=\"data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiI+PGRlZnM+PGxpbmVhckdyYWRpZW50IGlkPSJnIiB4MT0iMCIgeTE9IjAiIHgyPSIxIiB5Mj0iMSI+PHN0b3Agb2Zmc2V0PSIwIiBzdG9wLWNvbG9yPSIjMDI4NEM3Ii8+PHN0b3Agb2Zmc2V0PSIxIiBzdG9wLWNvbG9yPSIjMEQ5NDg4Ii8+PC9saW5lYXJHcmFkaWVudD48L2RlZnM+PHJlY3Qgd2lkdGg9IjMyIiBoZWlnaHQ9IjMyIiByeD0iNyIgZmlsbD0idXJsKCNnKSIvPjxnIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiPjxsaW5lIHgxPSIxNiIgeTE9IjE2IiB4Mj0iOCIgeTI9IjgiLz48bGluZSB4MT0iMTYiIHkxPSIxNiIgeDI9IjI0IiB5Mj0iOCIvPjxsaW5lIHgxPSIxNiIgeTE9IjE2IiB4Mj0iOCIgeTI9IjI0Ii8+PGxpbmUgeDE9IjE2IiB5MT0iMTYiIHgyPSIyNCIgeTI9IjI0Ii8+PC9nPjxnIGZpbGw9IiNmZmYiPjxjaXJjbGUgY3g9IjgiIGN5PSI4IiByPSIzIi8+PGNpcmNsZSBjeD0iMjQiIGN5PSI4IiByPSIzIi8+PGNpcmNsZSBjeD0iOCIgY3k9IjI0IiByPSIzIi8+PGNpcmNsZSBjeD0iMjQiIGN5PSIyNCIgcj0iMyIvPjxjaXJjbGUgY3g9IjE2IiBjeT0iMTYiIHI9IjMuNCIvPjwvZz48L3N2Zz4=\">\n<style>\n:root{\n  --paper:#EAEFF3; --surface:#FFFFFF; --surface-2:#F3F6F9; --ink:#16212C; --muted:#5A6A77;\n  --line:#D8E0E7; --line-2:#E7ECF1; --blue:#0284C7; --magenta:#0D9488; --green:#1F8A5B;\n  --green-bg:#E3F2EA; --red:#C23B3B; --red-bg:#F7E9E9; --amber:#B97C0C;\n  --shadow-sm:0 1px 2px rgba(22,33,44,.06), 0 1px 1px rgba(22,33,44,.04);\n  --shadow-md:0 2px 4px rgba(22,33,44,.05), 0 8px 20px -6px rgba(22,33,44,.12);\n  --shadow-lg:0 10px 36px -8px rgba(22,33,44,.18);\n  --shadow-pop:0 4px 10px rgba(22,33,44,.07), 0 16px 34px -8px rgba(2,132,199,.20);\n  --ring:rgba(2,132,199,.38);\n  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;\n  --sans:system-ui,-apple-system,\"Segoe UI\",Roboto,Helvetica,Arial,sans-serif;\n}\nbody.dark{\n  --paper:#1E2731; --surface:#27323D; --surface-2:#2F3B47; --ink:#E7EDF2; --muted:#9DAAB6;\n  --line:#3A4853; --line-2:#2F3B4700; --green-bg:#173E2C; --red-bg:#3A2222;\n  --blue:#38BDF8; --magenta:#2DD4BF;\n  --shadow-sm:0 1px 2px rgba(0,0,0,.35);\n  --shadow-md:0 2px 6px rgba(0,0,0,.4), 0 10px 26px -8px rgba(0,0,0,.5);\n  --shadow-lg:0 16px 44px -10px rgba(0,0,0,.6);\n  --shadow-pop:0 4px 10px rgba(0,0,0,.4), 0 18px 40px -10px rgba(56,189,248,.34);\n  --ring:rgba(56,189,248,.5);\n}\n*{box-sizing:border-box;margin:0;padding:0;}\nbody{\n  font-family:var(--sans);color:var(--ink);line-height:1.55;padding:0 16px 56px;\n  -webkit-font-smoothing:antialiased;min-height:100vh;\n  background:\n    radial-gradient(1100px 560px at 82% -12%, rgba(2,132,199,.07), transparent 60%),\n    radial-gradient(820px 480px at -12% 6%, rgba(13,148,136,.06), transparent 55%),\n    var(--paper);\n  background-attachment:fixed;\n}\nbody.dark{\n  background:\n    radial-gradient(1100px 560px at 82% -12%, rgba(56,189,248,.12), transparent 60%),\n    radial-gradient(820px 480px at -12% 4%, rgba(45,212,191,.10), transparent 55%),\n    var(--paper);\n  background-attachment:fixed;\n}\na{color:inherit;}\n.wrap{max-width:680px;margin:0 auto;}\n\n/* header */\nheader.top{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:22px 0 16px;border-bottom:1px solid var(--line);margin-bottom:24px;flex-wrap:wrap;}\n.brand a{text-decoration:none;}\n.brand-link{display:flex;align-items:center;gap:11px;}\n.brand .logo{flex:0 0 auto;width:40px;height:40px;border-radius:11px;overflow:hidden;display:block;box-shadow:var(--shadow-sm);}\n.brand .logo svg{display:block;width:40px;height:40px;}\n.brand h1{font-size:21px;font-weight:760;letter-spacing:-.02em;}\n.brand .tag{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--magenta);margin-top:3px;}\n.top nav{display:flex;gap:13px;font-size:13px;font-family:var(--mono);align-items:center;}\n.top nav a{color:var(--muted);text-decoration:none;transition:color .15s ease;}\n.top nav a:hover{color:var(--ink);}\n.user-chip{color:var(--ink);max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px;}\n.linkbtn{border:none;background:none;padding:0;color:var(--muted);font-family:var(--mono);font-size:13px;cursor:pointer;transition:color .15s ease;}\n.linkbtn:hover{color:var(--ink);box-shadow:none;transform:none;}\n\n/* theme toggle icon */\n.theme-toggle{display:inline-grid;place-items:center;width:34px;height:34px;border:1px solid var(--line);border-radius:9px;background:var(--surface);color:var(--muted);box-shadow:var(--shadow-sm);transition:transform .16s ease, box-shadow .16s ease, color .15s ease, border-color .15s ease;}\n.theme-toggle:hover{color:var(--ink);border-color:var(--blue);transform:translateY(-1px);box-shadow:var(--shadow-md);}\n.theme-toggle svg{display:block;}\n\n/* surfaces with depth */\n.tiles{display:flex;gap:12px;margin-bottom:22px;flex-wrap:wrap;}\n.tile{flex:1;min-width:120px;background:linear-gradient(180deg,var(--surface),var(--surface-2));border:1px solid var(--line);border-radius:14px;padding:16px 16px 15px;box-shadow:var(--shadow-md);position:relative;overflow:hidden;}\n.tile::before{content:\"\";position:absolute;left:0;top:0;height:3px;width:100%;background:linear-gradient(90deg,var(--blue),var(--magenta));opacity:.85;}\n.tile b{display:block;font-family:var(--mono);font-size:31px;line-height:1;font-weight:700;letter-spacing:-.02em;color:var(--ink);}\n.tile span{display:block;margin-top:7px;font-family:var(--mono);font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);}\n.section-title{font-family:var(--mono);font-size:12px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--ink);margin:30px 0 13px;display:flex;align-items:center;gap:9px;}\n.section-title::before{content:\"\";flex:0 0 auto;width:3px;height:13px;border-radius:2px;background:linear-gradient(180deg,var(--blue),var(--magenta));}\n.section-title::after{content:\"\";flex:1;height:1px;background:var(--line);}\n.cards{display:flex;flex-direction:column;gap:11px;}\n.actioncard{position:relative;display:block;background:linear-gradient(180deg,var(--surface),var(--surface-2));border:1px solid var(--line);border-radius:14px;padding:15px 42px 15px 70px;text-decoration:none;color:inherit;box-shadow:var(--shadow-md);transition:transform .18s ease, box-shadow .18s ease, border-color .18s ease;}\n.actioncard:hover{transform:translateY(-2px);box-shadow:var(--shadow-pop);border-color:var(--blue);}\n.actioncard b{font-size:15.5px;font-weight:680;letter-spacing:-.01em;color:var(--ink);}\n.actioncard > span{display:block;font-size:12.5px;color:var(--muted);margin-top:3px;line-height:1.45;}\n.actioncard .ic{position:absolute;left:14px;top:50%;transform:translateY(-50%);width:42px;height:42px;margin:0;border-radius:12px;display:grid;place-items:center;font-size:20px;line-height:1;font-style:normal;background:linear-gradient(155deg,rgba(2,132,199,.14),rgba(13,148,136,.12));border:1px solid var(--line-2);box-shadow:var(--shadow-sm);}\nbody.dark .actioncard .ic{background:linear-gradient(155deg,rgba(56,189,248,.20),rgba(45,212,191,.16));border-color:var(--line);}\n.actioncard::after{content:\"›\";position:absolute;right:18px;top:50%;transform:translateY(-50%);font-size:23px;line-height:1;color:var(--muted);opacity:.5;transition:transform .18s ease, opacity .18s ease, color .18s ease;}\n.actioncard:hover::after{transform:translateY(-50%) translateX(3px);opacity:1;color:var(--blue);}\n.hero{position:relative;display:block;border-radius:16px;padding:21px 48px 21px 78px;margin-bottom:11px;text-decoration:none;color:#fff;background:linear-gradient(145deg,#0EA5E9,#0284C7 52%,#0D9488);border:1px solid #0284C7;box-shadow:var(--shadow-lg);transition:transform .18s ease, box-shadow .18s ease;}\n.hero:hover{transform:translateY(-2px);box-shadow:var(--shadow-pop);}\n.hero b{display:block;font-size:18px;font-weight:700;letter-spacing:-.01em;color:#fff;line-height:1.2;}\n.hero > span{display:block;font-size:13px;color:rgba(255,255,255,.86);margin-top:4px;line-height:1.45;}\n.hero .ic{position:absolute;left:16px;top:50%;transform:translateY(-50%);width:46px;height:46px;margin:0;border-radius:13px;display:grid;place-items:center;font-size:23px;line-height:1;font-style:normal;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.32);}\n.hero::after{content:\"›\";position:absolute;right:20px;top:50%;transform:translateY(-50%);font-size:26px;line-height:1;color:rgba(255,255,255,.92);transition:transform .18s ease;}\n.hero:hover::after{transform:translateY(-50%) translateX(3px);}\n.bgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:11px;}\n.bcard{background:linear-gradient(180deg,var(--surface),var(--surface-2));border:1px solid var(--line);border-radius:14px;padding:14px 15px;text-decoration:none;color:inherit;box-shadow:var(--shadow-md);transition:transform .18s ease, box-shadow .18s ease, border-color .18s ease;}\n.bcard:hover{transform:translateY(-2px);box-shadow:var(--shadow-pop);border-color:var(--blue);}\n.bcard .n{font-family:var(--mono);font-size:11px;color:var(--magenta);text-transform:uppercase;letter-spacing:.06em;}\n.bcard .pct{font-family:var(--mono);font-size:13px;color:var(--muted);}\n.bar{height:6px;background:var(--line);border-radius:4px;margin-top:9px;overflow:hidden;box-shadow:inset 0 1px 2px rgba(0,0,0,.10);}\n.bar > i{display:block;height:6px;border-radius:4px;background:linear-gradient(90deg,var(--blue),var(--magenta));}\n\n/* practice + exam */\n.meta{display:flex;justify-content:space-between;align-items:center;font-family:var(--mono);font-size:11px;margin-bottom:14px;}\n.meta .l{color:var(--muted);}\n.meta .r{color:var(--blue);letter-spacing:.05em;}\n.qcard{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:22px;margin-bottom:16px;box-shadow:var(--shadow-lg);}\n.qtext{font-size:16px;line-height:1.6;}\n.code{font-family:var(--mono);font-size:13px;background:var(--surface-2);border:1px solid var(--line);border-radius:6px;padding:2px 6px;}\n.choices{display:flex;flex-direction:column;gap:9px;margin:0 0 16px;}\n.choice{display:flex;align-items:flex-start;gap:11px;padding:13px 15px;border:1px solid var(--line);border-radius:11px;background:var(--surface);font-size:15px;cursor:pointer;box-shadow:var(--shadow-sm);transition:transform .14s ease, box-shadow .14s ease, border-color .14s ease;}\n.choice:hover{transform:translateY(-1px);box-shadow:var(--shadow-md);border-color:var(--blue);}\n.choice input{margin-top:3px;accent-color:var(--blue);}\n.choice .cl{font-family:var(--mono);font-size:13px;opacity:.55;}\n.choice.correct{background:var(--green-bg);border-color:var(--green);}\n.choice.wrong{background:var(--red-bg);border-color:var(--red);}\n.choice.dim{opacity:.55;}\n.explain{border-radius:11px;padding:13px 15px;margin-bottom:16px;font-size:14px;line-height:1.6;box-shadow:var(--shadow-sm);}\n.explain.ok{background:var(--green-bg);border:1px solid var(--green);}\n.explain.bad{background:var(--red-bg);border:1px solid var(--red);}\n.explain .rl{font-family:var(--mono);font-size:10px;letter-spacing:.1em;text-transform:uppercase;opacity:.7;display:block;margin-bottom:4px;}\n\n/* buttons */\nbutton,.btn{font-family:var(--sans);font-size:15px;border-radius:10px;border:1px solid var(--line);background:var(--surface);color:var(--ink);padding:11px 16px;cursor:pointer;text-decoration:none;display:inline-block;box-shadow:var(--shadow-sm);transition:transform .16s ease, box-shadow .16s ease, border-color .16s ease;}\nbutton:hover,.btn:hover{border-color:var(--blue);transform:translateY(-1px);box-shadow:var(--shadow-md);}\n.btn-primary{background:linear-gradient(165deg,#0EA5E9,#0284C7);color:#fff;border-color:#0284C7;font-weight:600;width:100%;text-align:center;box-shadow:var(--shadow-md);}\n.btn-primary:hover{box-shadow:var(--shadow-pop);border-color:#0284C7;}\nbody.dark .btn-primary{background:linear-gradient(165deg,#0EA5E9,#0369A1);border-color:#0369A1;color:#fff;}\n.btn-row{display:flex;gap:8px;flex-wrap:wrap;}\n:focus-visible{outline:2px solid var(--ring);outline-offset:2px;}\n\n/* results */\n.bigpct{font-family:var(--mono);font-size:54px;font-weight:700;line-height:1;text-align:center;letter-spacing:-.02em;}\n.badge{display:inline-block;font-family:var(--mono);font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;padding:5px 13px;border-radius:999px;box-shadow:var(--shadow-sm);}\n.badge.pass{background:var(--green-bg);color:var(--green);border:1px solid var(--green);}\n.badge.fail{background:var(--red-bg);color:var(--red);border:1px solid var(--red);}\n.center{text-align:center;}\n.bdrow{display:flex;align-items:center;gap:10px;padding:5px 0;font-size:14px;}\n.bdrow .nm{width:110px;flex-shrink:0;}\n.bdrow .tr{flex:1;}\n.bdrow .vl{font-family:var(--mono);font-size:12px;width:84px;text-align:right;flex-shrink:0;}\n.palette{display:grid;grid-template-columns:repeat(10,1fr);gap:6px;margin:14px 0;}\n.palette button{padding:0;height:36px;font-family:var(--mono);font-size:12px;border-radius:8px;}\n.palette button.answered{background:var(--blue);color:#fff;border-color:var(--blue);}\n.palette button.current{outline:2px solid var(--magenta);outline-offset:1px;}\n\n/* review */\n.mbucket{margin-bottom:16px;}\n.mbname{font-family:var(--mono);font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:var(--magenta);margin-bottom:8px;}\n.mbname span{color:var(--muted);}\n.mcard{background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--magenta);border-radius:0 11px 11px 0;padding:11px 14px;margin-bottom:10px;box-shadow:var(--shadow-sm);}\n.mcard .mq{font-size:14px;margin-bottom:5px;}\n.mcard .ma{font-size:13.5px;color:var(--green);margin-bottom:3px;}\n.mcard .mr{font-size:13px;color:var(--muted);}\n.empty{text-align:center;color:var(--green);padding:18px 0;font-size:14px;}\n.timer{font-family:var(--mono);font-weight:700;}\n.timer.low{color:var(--red);}\n.filters{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px;}\n.filters a{font-family:var(--mono);font-size:12px;padding:6px 12px;border:1px solid var(--line);border-radius:8px;text-decoration:none;color:var(--muted);background:var(--surface);box-shadow:var(--shadow-sm);transition:transform .14s ease, border-color .14s ease, color .14s ease;}\n.filters a:hover{transform:translateY(-1px);border-color:var(--blue);color:var(--ink);}\n.filters a.active{background:var(--blue);color:#fff;border-color:var(--blue);}\n.note{font-family:var(--mono);font-size:11px;color:var(--muted);margin-top:28px;padding-top:14px;border-top:1px solid var(--line);}\n\n/* form fields */\n.field{width:100%;padding:11px 13px;border:1px solid var(--line);border-radius:10px;background:var(--surface);color:var(--ink);font-size:15px;box-shadow:var(--shadow-sm);transition:border-color .15s ease, box-shadow .15s ease;}\n.field:focus{outline:none;border-color:var(--blue);box-shadow:0 0 0 3px var(--ring);}\n.flabel{display:block;font-size:13px;color:var(--muted);margin-bottom:5px;}\n\n/* gentle load reveal */\n@keyframes rise{from{opacity:0;transform:translateY(9px);}to{opacity:1;transform:none;}}\n@media(prefers-reduced-motion:no-preference){\n  .tile,.actioncard,.bcard,.qcard,.meta,.mbucket,.bigpct,.badge,.acssummary,.ss-task{animation:rise .38s cubic-bezier(.2,.7,.3,1) both;}\n  .tile:nth-child(2),.actioncard:nth-child(2),.bcard:nth-child(2){animation-delay:.05s;}\n  .tile:nth-child(3),.actioncard:nth-child(3),.bcard:nth-child(3){animation-delay:.10s;}\n  .actioncard:nth-child(4),.bcard:nth-child(4){animation-delay:.14s;}\n}\n@media(max-width:480px){.palette{grid-template-columns:repeat(6,1fr);}.bgrid{grid-template-columns:1fr;}.user-chip{max-width:90px;}}\n\n/* icons, emojis, badges */\n.nav-ic{font-size:13px;margin-right:1px;}\n.tile{position:relative;}\n.tile .ic{position:absolute;top:13px;right:14px;font-size:17px;opacity:.9;line-height:1;}\n.bcard .ic{font-style:normal;margin-right:5px;}\n.bcard .n .ic{margin-right:5px;}\n.mbadge{display:inline-flex;align-items:center;gap:4px;font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;padding:3px 8px;border-radius:999px;border:1px solid var(--line);box-shadow:var(--shadow-sm);white-space:nowrap;}\n.mbadge.m-new{background:var(--surface-2);color:var(--muted);}\n.mbadge.m-master{background:rgba(185,124,12,.14);color:var(--amber);border-color:rgba(185,124,12,.45);}\n.mbadge.m-strong{background:var(--green-bg);color:var(--green);border-color:var(--green);}\n.mbadge.m-learn{background:rgba(43,92,158,.12);color:var(--blue);border-color:rgba(43,92,158,.4);}\n.mbadge.m-focus{background:var(--red-bg);color:var(--red);border-color:var(--red);}\n.bcard .top-row{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;}\n.countbadge{display:inline-flex;align-items:center;gap:4px;font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;padding:3px 9px;border-radius:999px;background:var(--red-bg);color:var(--red);border:1px solid var(--red);}\n.countbadge.ok{background:var(--green-bg);color:var(--green);border-color:var(--green);}\n.result-emoji{font-size:46px;line-height:1;margin-bottom:6px;}\n.badge .be{font-size:13px;margin-right:2px;}\n.choice .status{margin-left:auto;font-size:15px;align-self:center;}\n.feedback{display:flex;align-items:center;gap:9px;font-family:var(--mono);font-size:13px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;padding:11px 15px;border-radius:11px;margin-bottom:14px;box-shadow:var(--shadow-sm);}\n.feedback .fe{font-size:18px;}\n.feedback.ok{background:var(--green-bg);color:var(--green);border:1px solid var(--green);}\n.feedback.bad{background:var(--red-bg);color:var(--red);border:1px solid var(--red);}\n.bdrow .nm .ic{margin-right:5px;}\n.mbname .ic{margin-right:4px;}\n.filters a .ic{margin-right:3px;}\n.timer .te{margin-right:3px;}\n\n/* exam trend chart */\n.trend{position:relative;display:flex;align-items:flex-end;gap:6px;height:124px;padding-top:6px;border-bottom:1px solid var(--line);margin-bottom:8px;}\n.trend .tb{flex:1;min-width:7px;border-radius:5px 5px 0 0;box-shadow:var(--shadow-sm);}\n.trend .tb.pass{background:linear-gradient(180deg,#34b277,#1F8A5B);}\n.trend .tb.fail{background:linear-gradient(180deg,#db6060,#C23B3B);}\n.trend .passline{position:absolute;left:0;right:0;border-top:1px dashed var(--muted);opacity:.65;pointer-events:none;}\n.trend .passline span{position:absolute;right:0;top:-8px;font-family:var(--mono);font-size:9px;color:var(--muted);background:var(--paper);padding:0 4px;}\n\n/* cheat sheet */\n.cs-intro{font-size:14px;color:var(--muted);margin-bottom:18px;}\n.cs-group{margin-bottom:22px;}\n.cs-head{font-family:var(--mono);font-size:13px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--magenta);border-bottom:1px solid var(--line);padding-bottom:6px;margin-bottom:9px;display:flex;align-items:center;gap:7px;}\n.cs-head .cs-n{margin-left:auto;color:var(--muted);font-size:11px;}\n.cs-list{list-style:none;display:flex;flex-direction:column;gap:7px;}\n.cs-list li{font-size:14px;line-height:1.5;padding-left:18px;position:relative;}\n.cs-list li::before{content:\"\\203A\";position:absolute;left:4px;color:var(--blue);font-weight:700;}\n\n/* print-friendly output (Cmd/Ctrl + P) */\n@media print{\n  body{background:#fff;color:#000;padding:0;}\n  header.top,.note{display:none !important;}\n  .section-title::after{display:none;}\n  .cs-head{color:#000;border-color:#000;}\n  .cs-list li::before{color:#000;}\n  a{color:#000;text-decoration:none;}\n  .qcard,.actioncard,.tile,.bcard{box-shadow:none;}\n}\n\n.r .acs{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.82em;opacity:.72;cursor:help}\n\n/* ACS tasks to study (review screen) */\n.acssummary{border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:0 0 16px;background:var(--surface-2);}\n.acssummary-h{font-family:var(--mono);font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-bottom:8px;}\n.acsrow{display:flex;align-items:center;gap:10px;padding:4px 0;}\n.acsrow+.acsrow{border-top:1px solid var(--line);}\n.acsrow .acscode{font-family:var(--mono);font-size:12px;color:var(--blue);min-width:64px;}\n.acsrow .acstitle{flex:1;font-size:13px;color:var(--ink);}\n.acsrow .acsn{font-family:var(--mono);font-size:11px;color:var(--muted);}\n.macs{margin-top:7px;font-size:11px;color:var(--muted);font-family:var(--mono);}\n.macs .acs{color:var(--blue);cursor:help;}\n\n/* Sectional chart symbology legend (cheatsheet) */\n.csleg{background:#FAF8F2;border:1px solid #E3DCCB;border-radius:14px;padding:16px 16px 8px;margin:0 0 24px;color:#1c2733;}\n.csleg-note{font-size:12.5px;color:#5c6672;line-height:1.55;margin:0 0 6px;}\n.csleg-note b{color:#1c2733;}\n.csleg-h{font-family:var(--mono);font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#8a6d3b;margin:14px 0 8px;}\n.csleg-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:11px 16px;}\n.csleg-item{display:flex;align-items:center;gap:10px;}\n.csleg-sym{flex:0 0 52px;height:36px;background:#fff;border:1px solid #E3DCCB;border-radius:7px;}\n.csleg-sym svg{width:52px;height:36px;display:block;}\n.csleg-txt b{display:block;font-size:12.5px;font-weight:600;line-height:1.2;}\n.csleg-txt span{display:block;font-size:11px;color:#5c6672;line-height:1.3;margin-top:1px;}\n@media print{.csleg{background:#fff;}.csleg-sym{border-color:#ccc;}}\n\n/* Chart-reading figure (practice/learn/exam) */\n.figbox{background:#FAF8F2;border:1px solid #E3DCCB;border-radius:12px;padding:10px;margin:0 0 14px;}\n.figbox svg{display:block;width:100%;height:auto;aspect-ratio:660/400;}\n\n/* Personalized ACS study sheet */\n.ss-task{border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:0 0 12px;}\n.ss-head{display:flex;align-items:center;gap:10px;margin-bottom:8px;flex-wrap:wrap;}\n.ss-code{font-family:var(--mono);font-size:12px;font-weight:600;color:var(--blue);min-width:64px;}\n.ss-title{flex:1;font-weight:600;font-size:14px;}\n.ss-n{font-family:var(--mono);font-size:11px;color:var(--muted);}\n.ss-rules{margin:0;padding-left:20px;}\n.ss-rules li{font-size:13px;line-height:1.5;margin:3px 0;}\n@media print{.btn-row{display:none;}.ss-task{break-inside:avoid;}}\n\n</style>\n</head>\n<body class=\"{{ 'dark' if dark else '' }}\">\n<div class=\"wrap\">\n  <header class=\"top\">\n    <div class=\"brand\">\n      <a href=\"{{ url_for('home') }}\" class=\"brand-link\">\n        <span class=\"logo\" aria-hidden=\"true\">\n          <svg viewBox=\"0 0 32 32\" width=\"40\" height=\"40\"><defs><linearGradient id=\"logoGrad\" x1=\"0\" y1=\"0\" x2=\"1\" y2=\"1\"><stop offset=\"0\" stop-color=\"#0284C7\"/><stop offset=\"1\" stop-color=\"#0D9488\"/></linearGradient></defs><rect width=\"32\" height=\"32\" rx=\"8\" fill=\"url(#logoGrad)\"/><g stroke=\"#fff\" stroke-width=\"2\" stroke-linecap=\"round\"><line x1=\"16\" y1=\"16\" x2=\"8\" y2=\"8\"/><line x1=\"16\" y1=\"16\" x2=\"24\" y2=\"8\"/><line x1=\"16\" y1=\"16\" x2=\"8\" y2=\"24\"/><line x1=\"16\" y1=\"16\" x2=\"24\" y2=\"24\"/></g><g fill=\"#fff\"><circle cx=\"8\" cy=\"8\" r=\"3\"/><circle cx=\"24\" cy=\"8\" r=\"3\"/><circle cx=\"8\" cy=\"24\" r=\"3\"/><circle cx=\"24\" cy=\"24\" r=\"3\"/><circle cx=\"16\" cy=\"16\" r=\"3.4\"/></g></svg>\n        </span>\n        <span class=\"brand-text\">\n          <h1>Part 107 Ground School</h1>\n          <div class=\"tag\">FAA prep</div>\n        </span>\n      </a>\n    </div>\n    <nav>\n      <a href=\"{{ url_for('home') }}\"><span class=\"nav-ic\">🏠</span> Home</a>\n      <a href=\"{{ url_for('review') }}\"><span class=\"nav-ic\">📚</span> Study list</a>\n      <a href=\"{{ url_for('history') }}\"><span class=\"nav-ic\">📈</span> Progress</a>\n      <a class=\"theme-toggle\" href=\"{{ url_for('toggle_theme') }}\"\n         aria-label=\"{{ 'Switch to light mode' if dark else 'Switch to dark mode' }}\"\n         title=\"{{ 'Light mode' if dark else 'Dark mode' }}\">\n        {% if dark %}\n        <svg width=\"17\" height=\"17\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><circle cx=\"12\" cy=\"12\" r=\"4\"/><path d=\"M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41\"/></svg>\n        {% else %}\n        <svg width=\"17\" height=\"17\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z\"/></svg>\n        {% endif %}\n      </a>\n      {% if user %}\n      <span class=\"user-chip\" title=\"{{ user.email }}\">{{ user.email }}</span>\n      <form method=\"post\" action=\"{{ url_for('logout') }}\" style=\"display:inline;margin:0\">\n        <input type=\"hidden\" name=\"_csrf\" value=\"{{ csrf_token }}\">\n        <button type=\"submit\" class=\"linkbtn\">Sign out</button>\n      </form>\n      {% else %}\n      <a href=\"{{ url_for('login') }}\">Sign in</a>\n      {% endif %}\n    </nav>\n  </header>\n  {% block body %}{% endblock %}\n  <div class=\"note\">{% if user %}Signed in as {{ user.email }}. Progress syncs to your account across devices.{% else %}Progress saves on this server for this browser. Sign in to sync across devices.{% endif %}</div>\n</div>\n</body>\n</html>\n", "practice.html": "{% extends \"base.html\" %}\n{% block body %}\n{% if drill_empty %}\n<div class=\"section-title\">🎯 Drill misses</div>\n<div class=\"empty\">🎉 No missed questions{{ ' in this topic' if drill_bucket }} to drill right now. Miss some in practice or the exam and they will collect here for focused drilling.</div>\n<div class=\"center\" style=\"margin-top:8px\"><a class=\"btn\" href=\"{{ url_for('home') }}\">🏠 Home</a> <a class=\"btn\" href=\"{{ url_for('practice', bucket='All') }}\">✍️ Practice all</a></div>\n{% else %}\n<div class=\"meta\">\n  <span class=\"l\">{% if figmode %}🗺️ Chart reading{% elif mode == 'drill' %}🎯 Drill misses{% elif mode == 'focus' %}🎚️ Focus practice{% else %}✍️ Practice{% endif %}</span>\n  <span class=\"r\">{{ icons[q.b] }} {{ q.b }} &middot; {{ q.s }}{% if q.acs %} &middot; <span class=\"acs\" title=\"{{ acs_tasks[q.acs] }}\">{{ q.acs }}</span>{% endif %}</span>\n</div>\n\n{% if not answered %}\n<form method=\"post\" action=\"{{ url_for('practice_answer') }}\">\n  <input type=\"hidden\" name=\"_csrf\" value=\"{{ csrf_token }}\">\n  <input type=\"hidden\" name=\"qid\" value=\"{{ q.id }}\">\n  <input type=\"hidden\" name=\"bucket\" value=\"{{ bucket }}\">\n  <input type=\"hidden\" name=\"mode\" value=\"{{ mode }}\">\n  <input type=\"hidden\" name=\"dbucket\" value=\"{{ drill_bucket or '' }}\">\n  <input type=\"hidden\" name=\"figures\" value=\"{{ figmode or '' }}\">\n  {% if q.fig %}<div class=\"figbox\">{{ figures[q.fig]|safe }}</div>{% endif %}<div class=\"qcard\"><p class=\"qtext\">{{ q.q_html|safe }}</p></div>\n  <div class=\"choices\">\n    {% for c in choices %}\n    <label class=\"choice\">\n      <input type=\"radio\" name=\"choice\" value=\"{{ c.idx }}\" required>\n      <span class=\"cl\">{{ c.letter }}</span><span>{{ c.text }}</span>\n    </label>\n    {% endfor %}\n  </div>\n  <button type=\"submit\" class=\"btn-primary\">Check answer</button>\n</form>\n{% else %}\n  {% if q.fig %}<div class=\"figbox\">{{ figures[q.fig]|safe }}</div>{% endif %}<div class=\"qcard\"><p class=\"qtext\">{{ q.q_html|safe }}</p></div>\n  <div class=\"feedback {{ 'ok' if correct else 'bad' }}\">\n    <span class=\"fe\">{{ '✅' if correct else '❌' }}</span>{{ 'Correct' if correct else 'Not quite' }}\n  </div>\n  <div class=\"choices\">\n    {% for c in choices %}\n    <div class=\"choice {{ 'correct' if c.idx == q.a else ('wrong' if c.idx == chosen else 'dim') }}\">\n      <span class=\"cl\">{{ c.letter }}</span><span>{{ c.text }}</span>\n      {% if c.idx == q.a %}<span class=\"status\">✅</span>{% elif c.idx == chosen %}<span class=\"status\">❌</span>{% endif %}\n    </div>\n    {% endfor %}\n  </div>\n  <div class=\"explain {{ 'ok' if correct else 'bad' }}\">\n    <span class=\"rl\">{{ '✅ correct &middot; the rule'|safe if correct else '📌 the rule'|safe }}</span>{{ q.e }}\n  </div>\n  <a class=\"btn-primary\" href=\"{% if mode == 'drill' %}{{ url_for('drill', bucket=drill_bucket) }}{% elif mode == 'focus' %}{{ url_for('focus') }}{% else %}{{ url_for('practice', bucket=bucket, figures=figmode) if figmode else url_for('practice', bucket=bucket) }}{% endif %}\">{% if mode == 'drill' %}🎯 Next missed{% elif mode == 'focus' %}🎚️ Next focus{% else %}{{ 'Next chart' if figmode else 'Next question' }}{% endif %}</a>\n  <div class=\"center\" style=\"margin-top:12px\"><a href=\"{{ url_for('home') }}\" style=\"font-size:13px;color:var(--muted)\">Back to home</a></div>\n{% endif %}\n{% endif %}\n{% endblock %}\n", "studysheet.html": "{% extends \"base.html\" %}\n{% block body %}\n<div class=\"section-title\">🎯 Your ACS study sheet</div>\n{% if tasks %}\n<p class=\"cs-intro\">Your weak ACS tasks, built from the {{ total_missed }} question{{ 's' if total_missed != 1 }} you have missed, ordered by how often you missed them. Each task lists the rules to review. Generated {{ generated }}; use your browser's print (Cmd or Ctrl + P) to save a copy.</p>\n{% for t in tasks %}\n<div class=\"ss-task\">\n  <div class=\"ss-head\"><span class=\"ss-code\">{{ t.code }}</span><span class=\"ss-title\">{{ t.title }}</span><span class=\"ss-n\">{{ t.misses }} miss{{ 'es' if t.misses != 1 }} &middot; {{ t.qcount }} question{{ 's' if t.qcount != 1 }}</span></div>\n  <ul class=\"ss-rules\">\n    {% for r in t.rules %}<li>{{ r }}</li>\n    {% endfor %}\n  </ul>\n</div>\n{% endfor %}\n{% else %}\n<div class=\"empty\">🌟 Nothing missed yet. Take a practice exam or some practice questions, and the ACS tasks you need to study will show up here.</div>\n{% endif %}\n<div class=\"btn-row\" style=\"margin-top:14px\">\n  <a class=\"btn\" href=\"{{ url_for('review') }}\">📚 Study list</a>\n  {% if tasks %}<a class=\"btn\" href=\"{{ url_for('drill') }}\">🎯 Drill misses</a>{% endif %}\n  <a class=\"btn\" href=\"{{ url_for('home') }}\">🏠 Home</a>\n</div>\n{% endblock %}\n"}'''
TEMPLATES = json.loads(TEMPLATES_JSON)

ROOT = Path(__file__).resolve().parent
app = Flask(__name__)
app.jinja_loader = DictLoader(TEMPLATES)


def _secret_key():
    env = os.environ.get("FLASK_SECRET_KEY")
    if env:
        return env
    path = ROOT / ".flask_secret"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    key = secrets.token_hex(32)
    try:
        path.write_text(key, encoding="utf-8")
    except OSError:
        pass
    return key


app.secret_key = _secret_key()

# Cookie hardening. Secure is off for local HTTP so login works in development;
# set SESSION_COOKIE_SECURE=1 (or serve over HTTPS) to send cookies only over TLS.
_SECURE_COOKIES = os.environ.get("SESSION_COOKIE_SECURE", "").strip().lower() in ("1", "true", "yes", "on")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=_SECURE_COOKIES,
)

# ---- Data -------------------------------------------------------------------
QUESTIONS = json.loads(QUESTIONS_JSON)
for i, q in enumerate(QUESTIONS):
    q["id"] = i

BUCKETS = ["Regulations", "Airspace", "Charts", "Weather", "Operations", "Loading"]
BUCKET_ICONS = {
    "Regulations": "\U0001F4CB",   # clipboard
    "Airspace": "\U0001F5FA\uFE0F",  # map
    "Charts": "\U0001F9ED",         # compass
    "Weather": "\U0001F326\uFE0F",   # sun behind rain cloud
    "Operations": "\U0001F681",     # helicopter
    "Loading": "\u2696\uFE0F",       # balance scale
}


def mastery_badge(pct):
    """Return a small achievement badge for a topic given its accuracy."""
    if pct is None:
        return {"emoji": "\U0001F195", "label": "New", "cls": "m-new"}
    if pct >= 90:
        return {"emoji": "\U0001F3C6", "label": "Master", "cls": "m-master"}
    if pct >= 75:
        return {"emoji": "\u2B50", "label": "Strong", "cls": "m-strong"}
    if pct >= 50:
        return {"emoji": "\U0001F331", "label": "Learning", "cls": "m-learn"}
    return {"emoji": "\U0001F3AF", "label": "Focus", "cls": "m-focus"}


LETTERS = "ABCD"
EXAM_N = min(65, len(QUESTIONS))
EXAM_EXPERIMENTAL = 5 if EXAM_N > 5 else 0
EXAM_SCORED = EXAM_N - EXAM_EXPERIMENTAL
EXAM_PASS = 70
EXAM_MIN = 120

# Target share of the SCORED questions per topic, modeled on the FAA UAS ACS
# knowledge-area weighting (Operations 35-45%, Regulations 15-25%, Airspace
# 15-25%, Weather 11-16%, Loading 7-11%). Sectional chart reading is a skill
# folded into Airspace in the ACS, so Charts is given a small share carved from
# the Airspace band. These are midpoints and are safe to tune; they need not
# sum to exactly 1 (they are normalized at apportionment time).
EXAM_BLUEPRINT = {
    "Operations": 0.36,
    "Regulations": 0.20,
    "Airspace": 0.16,
    "Weather": 0.12,
    "Loading": 0.08,
    "Charts": 0.08,
}
CODE_SUBTOPICS = {"METAR", "TAF", "Winds Aloft"}

# ACS task codes (FAA-S-ACS-10B structure) -> human-readable titles, shown next
# to a question so a learner can map it to the Airman Certification Standards.
ACS_TASKS = {
    "UA.I.A": "Regulations - General",
    "UA.I.B": "Regulations - Operating Rules",
    "UA.I.C": "Regulations - Remote Pilot Certification",
    "UA.I.D": "Regulations - Waivers",
    "UA.I.E": "Regulations - Operations Over People",
    "UA.I.F": "Regulations - Remote Identification",
    "UA.II.A": "Airspace - Classification",
    "UA.II.B": "Airspace - Operational Requirements",
    "UA.III.A": "Weather - Sources of Weather",
    "UA.III.B": "Weather - Effects of Weather on Performance",
    "UA.IV.A": "Loading and Performance",
    "UA.V.A": "Operations - Radio Communications Procedures",
    "UA.V.B": "Operations - Airport Operations",
    "UA.V.C": "Operations - Emergency Procedures",
    "UA.V.D": "Operations - Aeronautical Decision-Making",
    "UA.V.E": "Operations - Physiology",
    "UA.V.F": "Operations - Maintenance and Inspection Procedures",
}

# Figure registry for chart-reading questions. A question with a "fig" key
# renders the matching original SVG sectional excerpt above its text. Several
# questions can share one figure. These are study aids, not for navigation.
FIGURES = {
    "sectional_poc_1": (
        '<svg viewBox="0 0 660 400" width="660" height="400" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Practice sectional chart excerpt"><rect width="660" height="400" fill="#FAF8F2"/><g stroke="#E7E0CF" stroke-width="1"><line x1="0" y1="133" x2="660" y2="133"/><line x1="0" y1="266" x2="660" y2="266"/><line x1="220" y1="0" x2="220" y2="400"/><line x1="440" y1="0" x2="440" y2="400"/></g><text x="556" y="80" font-family="monospace" font-weight="800" font-size="34" fill="#6b6450">2</text><text x="582" y="62" font-family="monospace" font-weight="800" font-size="20" fill="#6b6450">5</text><circle cx="180" cy="212" r="82" fill="none" stroke="#2E5AAC" stroke-width="2" stroke-dasharray="9 6"/><rect x="163" y="116" width="34" height="22" fill="#FAF8F2" stroke="#2E5AAC" stroke-width="1.4" stroke-dasharray="4 3"/><text x="180" y="132" font-family="monospace" font-weight="700" font-size="13" fill="#2E5AAC" text-anchor="middle">25</text><g fill="none" stroke="#2E5AAC" stroke-width="2.4"><circle cx="180" cy="212" r="13"/></g><g stroke="#2E5AAC" stroke-width="2.6" stroke-linecap="round"><line x1="169" y1="212" x2="191" y2="212"/><line x1="173" y1="203" x2="187" y2="221"/></g><circle cx="146" cy="240" r="12" fill="#1c2733"/><text x="146" y="245" font-family="sans-serif" font-weight="700" font-size="14" fill="#fff" text-anchor="middle">1</text><g fill="none" stroke="#B0327D" stroke-width="2.4"><circle cx="516" cy="150" r="13"/></g><g stroke="#B0327D" stroke-width="2.6" stroke-linecap="round"><line x1="505" y1="150" x2="527" y2="150"/><line x1="509" y1="141" x2="523" y2="159"/></g><circle cx="516" cy="182" r="12" fill="#1c2733"/><text x="516" y="187" font-family="sans-serif" font-weight="700" font-size="14" fill="#fff" text-anchor="middle">2</text><path d="M422 322 L430 290 L438 322" fill="none" stroke="#1c2733" stroke-width="2.4"/><circle cx="430" cy="322" r="2.4" fill="#1c2733"/><text x="446" y="312" font-family="monospace" font-weight="700" font-size="13" fill="#1c2733">1549</text><text x="446" y="328" font-family="monospace" font-size="12" fill="#1c2733">(549)</text><circle cx="402" cy="314" r="12" fill="#1c2733"/><text x="402" y="319" font-family="sans-serif" font-weight="700" font-size="14" fill="#fff" text-anchor="middle">3</text><text x="14" y="390" font-family="monospace" font-size="11" fill="#8a6d3b">Practice excerpt, not for navigation</text></svg>'
    ),
    "sectional_class_c": (
        '<svg viewBox="0 0 660 400" width="660" height="400" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Practice sectional: Class C and Class E surface"><rect width="660" height="400" fill="#FAF8F2"/><g stroke="#E7E0CF" stroke-width="1"><line x1="0" y1="133" x2="660" y2="133"/><line x1="0" y1="266" x2="660" y2="266"/><line x1="220" y1="0" x2="220" y2="400"/><line x1="440" y1="0" x2="440" y2="400"/></g><circle cx="178" cy="206" r="98" fill="none" stroke="#B0327D" stroke-width="2.6"/><circle cx="178" cy="206" r="56" fill="none" stroke="#B0327D" stroke-width="2.6"/><g fill="none" stroke="#2E5AAC" stroke-width="2.4"><circle cx="178" cy="206" r="13"/></g><g stroke="#2E5AAC" stroke-width="2.6" stroke-linecap="round"><line x1="167" y1="206" x2="189" y2="206"/><line x1="171" y1="197" x2="185" y2="215"/></g><circle cx="247" cy="137" r="12" fill="#1c2733"/><text x="247" y="142" font-family="sans-serif" font-weight="700" font-size="14" fill="#fff" text-anchor="middle">1</text><circle cx="512" cy="296" r="64" fill="none" stroke="#B0327D" stroke-width="2.4" stroke-dasharray="8 5"/><g fill="none" stroke="#B0327D" stroke-width="2.4"><circle cx="512" cy="296" r="13"/></g><g stroke="#B0327D" stroke-width="2.6" stroke-linecap="round"><line x1="501" y1="296" x2="523" y2="296"/><line x1="505" y1="287" x2="519" y2="305"/></g><circle cx="512" cy="232" r="12" fill="#1c2733"/><text x="512" y="237" font-family="sans-serif" font-weight="700" font-size="14" fill="#fff" text-anchor="middle">2</text><text x="14" y="390" font-family="monospace" font-size="11" fill="#8a6d3b">Practice excerpt, not for navigation</text></svg>'
    ),
    "sectional_ceilfloor": (
        '<svg viewBox="0 0 660 400" width="660" height="400" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Practice sectional: reading airspace ceilings and floors"><rect width="660" height="400" fill="#FAF8F2"/><g stroke="#E7E0CF" stroke-width="1"><line x1="0" y1="133" x2="660" y2="133"/><line x1="0" y1="266" x2="660" y2="266"/><line x1="220" y1="0" x2="220" y2="400"/><line x1="440" y1="0" x2="440" y2="400"/></g><defs><linearGradient id="ce700" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#B0327D" stop-opacity=".50"/><stop offset="1" stop-color="#B0327D" stop-opacity="0"/></linearGradient></defs><rect x="104" y="146" width="92" height="74" rx="9" fill="none" stroke="#D9D2C2" stroke-width="1.4"/><text x="150" y="172" font-family="monospace" font-weight="700" font-size="17" fill="#1c2733" text-anchor="middle">55</text><line x1="132" y1="176" x2="168" y2="176" stroke="#1c2733" stroke-width="1.4"/><text x="150" y="193" font-family="monospace" font-weight="700" font-size="17" fill="#1c2733" text-anchor="middle">12</text><circle cx="150" cy="250" r="12" fill="#1c2733"/><text x="150" y="255" font-family="sans-serif" font-weight="700" font-size="14" fill="#fff" text-anchor="middle">1</text><line x1="300" y1="120" x2="624" y2="120" stroke="#2E5AAC" stroke-width="3.4"/><text x="452" y="146" font-family="monospace" font-weight="700" font-size="17" fill="#1c2733" text-anchor="middle">100</text><line x1="434" y1="150" x2="470" y2="150" stroke="#1c2733" stroke-width="1.4"/><text x="452" y="167" font-family="monospace" font-weight="700" font-size="17" fill="#1c2733" text-anchor="middle">SFC</text><circle cx="452" cy="196" r="12" fill="#1c2733"/><text x="452" y="201" font-family="sans-serif" font-weight="700" font-size="14" fill="#fff" text-anchor="middle">2</text><rect x="430" y="298" width="202" height="56" fill="url(#ce700)"/><line x1="430" y1="298" x2="632" y2="298" stroke="#B0327D" stroke-width="2" opacity=".85"/><circle cx="531" cy="332" r="12" fill="#1c2733"/><text x="531" y="337" font-family="sans-serif" font-weight="700" font-size="14" fill="#fff" text-anchor="middle">3</text><text x="14" y="390" font-family="monospace" font-size="11" fill="#8a6d3b">Practice excerpt, not for navigation</text></svg>'
    ),
    "sectional_sua": (
        '<svg viewBox="0 0 660 400" width="660" height="400" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Practice sectional: special use airspace and checkpoint"><rect width="660" height="400" fill="#FAF8F2"/><g stroke="#E7E0CF" stroke-width="1"><line x1="0" y1="133" x2="660" y2="133"/><line x1="0" y1="266" x2="660" y2="266"/><line x1="220" y1="0" x2="220" y2="400"/><line x1="440" y1="0" x2="440" y2="400"/></g><rect x="60" y="80" width="248" height="148" rx="6" fill="none" stroke="#2E5AAC" stroke-width="2.4"/><line x1="78" y1="92" x2="69" y2="80" stroke="#2E5AAC" stroke-width="1.8"/><line x1="104" y1="92" x2="95" y2="80" stroke="#2E5AAC" stroke-width="1.8"/><line x1="130" y1="92" x2="121" y2="80" stroke="#2E5AAC" stroke-width="1.8"/><line x1="156" y1="92" x2="147" y2="80" stroke="#2E5AAC" stroke-width="1.8"/><line x1="182" y1="92" x2="173" y2="80" stroke="#2E5AAC" stroke-width="1.8"/><line x1="208" y1="92" x2="199" y2="80" stroke="#2E5AAC" stroke-width="1.8"/><line x1="234" y1="92" x2="225" y2="80" stroke="#2E5AAC" stroke-width="1.8"/><line x1="260" y1="92" x2="251" y2="80" stroke="#2E5AAC" stroke-width="1.8"/><line x1="286" y1="92" x2="277" y2="80" stroke="#2E5AAC" stroke-width="1.8"/><line x1="72" y1="104" x2="60" y2="95" stroke="#2E5AAC" stroke-width="1.8"/><line x1="72" y1="130" x2="60" y2="121" stroke="#2E5AAC" stroke-width="1.8"/><line x1="72" y1="156" x2="60" y2="147" stroke="#2E5AAC" stroke-width="1.8"/><line x1="72" y1="182" x2="60" y2="173" stroke="#2E5AAC" stroke-width="1.8"/><line x1="72" y1="208" x2="60" y2="199" stroke="#2E5AAC" stroke-width="1.8"/><text x="184" y="150" font-family="monospace" font-weight="700" font-size="18" fill="#2E5AAC" text-anchor="middle">R-2501</text><text x="184" y="172" font-family="monospace" font-size="12" fill="#2E5AAC" text-anchor="middle">to 8000 / SFC</text><circle cx="120" cy="108" r="12" fill="#1c2733"/><text x="120" y="113" font-family="sans-serif" font-weight="700" font-size="14" fill="#fff" text-anchor="middle">1</text><line x1="428" y1="236" x2="428" y2="292" stroke="#B0327D" stroke-width="2.2"/><path d="M428 238 L456 246 L428 254 Z" fill="#B0327D"/><circle cx="428" cy="312" r="12" fill="#1c2733"/><text x="428" y="317" font-family="sans-serif" font-weight="700" font-size="14" fill="#fff" text-anchor="middle">2</text><line x1="330" y1="366" x2="624" y2="338" stroke="#2E5AAC" stroke-width="1.7"/><text x="470" y="346" font-family="monospace" font-size="11" fill="#2E5AAC" text-anchor="middle">V23</text><circle cx="575" cy="344" r="12" fill="#1c2733"/><text x="575" y="349" font-family="sans-serif" font-weight="700" font-size="14" fill="#fff" text-anchor="middle">3</text><text x="14" y="390" font-family="monospace" font-size="11" fill="#8a6d3b">Practice excerpt, not for navigation</text></svg>'
    ),
    "sectional_class_b": (
        '<svg viewBox="0 0 660 400" width="660" height="400" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Practice sectional: Class B airspace"><rect width="660" height="400" fill="#FAF8F2"/><g stroke="#E7E0CF" stroke-width="1"><line x1="0" y1="133" x2="660" y2="133"/><line x1="0" y1="266" x2="660" y2="266"/><line x1="220" y1="0" x2="220" y2="400"/><line x1="440" y1="0" x2="440" y2="400"/></g><circle cx="196" cy="208" r="104" fill="none" stroke="#2E5AAC" stroke-width="2.8"/><circle cx="196" cy="208" r="62" fill="none" stroke="#2E5AAC" stroke-width="2.8"/><g fill="none" stroke="#2E5AAC" stroke-width="2.4"><circle cx="196" cy="208" r="13"/></g><g stroke="#2E5AAC" stroke-width="2.6" stroke-linecap="round"><line x1="185" y1="208" x2="207" y2="208"/><line x1="189" y1="199" x2="203" y2="217"/></g><circle cx="264" cy="131" r="12" fill="#1c2733"/><text x="264" y="136" font-family="sans-serif" font-weight="700" font-size="14" fill="#fff" text-anchor="middle">1</text><text x="404" y="146" font-family="monospace" font-weight="700" font-size="17" fill="#2E5AAC" text-anchor="middle">100</text><line x1="386" y1="150" x2="422" y2="150" stroke="#2E5AAC" stroke-width="1.4"/><text x="404" y="167" font-family="monospace" font-weight="700" font-size="17" fill="#2E5AAC" text-anchor="middle">30</text><circle cx="404" cy="196" r="12" fill="#1c2733"/><text x="404" y="201" font-family="sans-serif" font-weight="700" font-size="14" fill="#fff" text-anchor="middle">2</text><text x="196" y="296" font-family="monospace" font-weight="700" font-size="17" fill="#2E5AAC" text-anchor="middle">100</text><line x1="178" y1="300" x2="214" y2="300" stroke="#2E5AAC" stroke-width="1.4"/><text x="196" y="317" font-family="monospace" font-weight="700" font-size="17" fill="#2E5AAC" text-anchor="middle">SFC</text><text x="14" y="390" font-family="monospace" font-size="11" fill="#8a6d3b">Practice excerpt, not for navigation</text></svg>'
    ),
    "sectional_symbols": (
        '<svg viewBox="0 0 660 400" width="660" height="400" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Practice sectional: routes and special symbols"><rect width="660" height="400" fill="#FAF8F2"/><g stroke="#E7E0CF" stroke-width="1"><line x1="0" y1="133" x2="660" y2="133"/><line x1="0" y1="266" x2="660" y2="266"/><line x1="220" y1="0" x2="220" y2="400"/><line x1="440" y1="0" x2="440" y2="400"/></g><line x1="40" y1="70" x2="430" y2="150" stroke="#6b6450" stroke-width="2.2"/><text x="150" y="95" font-family="monospace" font-weight="700" font-size="14" fill="#6b6450">VR1234</text><circle cx="300" cy="128" r="12" fill="#1c2733"/><text x="300" y="133" font-family="sans-serif" font-weight="700" font-size="14" fill="#fff" text-anchor="middle">1</text><path d="M250 250 A34 34 0 0 1 318 250" fill="none" stroke="#2E5AAC" stroke-width="2.4"/><g stroke="#2E5AAC" stroke-width="1.6"><line x1="252" y1="250" x2="284" y2="284"/><line x1="316" y1="250" x2="284" y2="284"/><line x1="284" y1="250" x2="284" y2="284"/></g><circle cx="284" cy="290" r="3.2" fill="#2E5AAC"/><circle cx="330" cy="272" r="12" fill="#1c2733"/><text x="330" y="277" font-family="sans-serif" font-weight="700" font-size="14" fill="#fff" text-anchor="middle">2</text><circle cx="516" cy="196" r="20" fill="none" stroke="#B0327D" stroke-width="2.2"/><g stroke="#B0327D" stroke-width="2" fill="none" stroke-linecap="round"><line x1="516" y1="184" x2="516" y2="210"/><circle cx="516" cy="182" r="2.6" fill="#B0327D" stroke="none"/><line x1="508" y1="192" x2="524" y2="192"/><path d="M506 202 A10 10 0 0 0 526 202"/></g><circle cx="548" cy="170" r="12" fill="#1c2733"/><text x="548" y="175" font-family="sans-serif" font-weight="700" font-size="14" fill="#fff" text-anchor="middle">3</text><text x="14" y="390" font-family="monospace" font-size="11" fill="#8a6d3b">Practice excerpt, not for navigation</text></svg>'
    ),
    "sectional_point_airspace": (
        '<svg viewBox="0 0 660 400" width="660" height="400" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Practice sectional: identifying airspace at a point"><rect width="660" height="400" fill="#FAF8F2"/><g stroke="#E7E0CF" stroke-width="1"><line x1="0" y1="133" x2="660" y2="133"/><line x1="0" y1="266" x2="660" y2="266"/><line x1="220" y1="0" x2="220" y2="400"/><line x1="440" y1="0" x2="440" y2="400"/></g><defs><linearGradient id="pa700" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#B0327D" stop-opacity=".50"/><stop offset="1" stop-color="#B0327D" stop-opacity="0"/></linearGradient></defs><circle cx="172" cy="206" r="80" fill="none" stroke="#2E5AAC" stroke-width="2" stroke-dasharray="9 6"/><rect x="155" y="114" width="34" height="22" fill="#FAF8F2" stroke="#2E5AAC" stroke-width="1.4" stroke-dasharray="4 3"/><text x="172" y="130" font-family="monospace" font-weight="700" font-size="13" fill="#2E5AAC" text-anchor="middle">27</text><g fill="none" stroke="#2E5AAC" stroke-width="2.4"><circle cx="172" cy="206" r="13"/></g><g stroke="#2E5AAC" stroke-width="2.6" stroke-linecap="round"><line x1="161" y1="206" x2="183" y2="206"/><line x1="165" y1="197" x2="179" y2="215"/></g><circle cx="116" cy="250" r="12" fill="#1c2733"/><text x="116" y="255" font-family="sans-serif" font-weight="700" font-size="14" fill="#fff" text-anchor="middle">1</text><rect x="478" y="96" width="92" height="210" fill="url(#pa700)"/><line x1="478" y1="96" x2="478" y2="306" stroke="#B0327D" stroke-width="2" opacity=".85"/><circle cx="556" cy="200" r="12" fill="#1c2733"/><text x="556" y="205" font-family="sans-serif" font-weight="700" font-size="14" fill="#fff" text-anchor="middle">2</text><circle cx="300" cy="338" r="12" fill="#1c2733"/><text x="300" y="343" font-family="sans-serif" font-weight="700" font-size="14" fill="#fff" text-anchor="middle">3</text><text x="14" y="390" font-family="monospace" font-size="11" fill="#8a6d3b">Practice excerpt, not for navigation</text></svg>'
    ),
}

# ---- Per-browser progress store (file-based) --------------------------------
STORE_FILE = ROOT / "progress_store.json"
_lock = threading.Lock()
COOKIE = "p107_uid"
_UID_RE = re.compile(r"^[a-f0-9]{32}$")


def _fresh():
    return {"lifetime": {}, "missed": {}, "sessions": [],
            "prefs": {"dark": False}, "exam": None}


def _read_all():
    if STORE_FILE.exists():
        try:
            return json.loads(STORE_FILE.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {}
    return {}


def _write_all(data):
    STORE_FILE.write_text(json.dumps(data), encoding="utf-8")


def get_record(uid):
    rec = _read_all().get(uid)
    if not isinstance(rec, dict):
        return _fresh()
    base = _fresh()
    base.update(rec)
    base["prefs"] = {**{"dark": False}, **(rec.get("prefs") or {})}
    return base


def save_record(uid, rec):
    with _lock:
        data = _read_all()
        data[uid] = rec
        _write_all(data)


# ---- User accounts (file-based) ---------------------------------------------
USERS_FILE = ROOT / "users.json"
_users_lock = threading.Lock()
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def read_users():
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {}
    return {}


def write_users(users):
    with _users_lock:
        USERS_FILE.write_text(json.dumps(users), encoding="utf-8")


def validate_credentials(email, password):
    if not _EMAIL_RE.match(email or ""):
        return "Enter a valid email address."
    if len(password or "") < 6:
        return "Password must be at least 6 characters."
    return None


def migrate_device_to_user(user_id):
    """When an account has no progress yet, adopt this browser's anonymous progress."""
    urec = get_record("u:" + user_id)
    drec = get_record("d:" + g.uid)
    user_empty = not (urec["lifetime"] or urec["missed"] or urec["sessions"])
    device_has = drec["lifetime"] or drec["missed"] or drec["sessions"]
    if user_empty and device_has:
        for k in ("lifetime", "missed", "sessions", "prefs"):
            urec[k] = drec[k]
        save_record("u:" + user_id, urec)


# ---- Helpers ----------------------------------------------------------------
def q_html(q):
    t = q["q"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    if q.get("s") in CODE_SUBTOPICS:
        t = re.sub(r"'([^']+)'", r'<span class="code">\1</span>', t)
    return Markup(t)


def shuffled(order, q):
    return [{"idx": oi, "letter": LETTERS[i], "text": q["c"][oi]}
            for i, oi in enumerate(order)]


def color_for(pct):
    if pct is None:
        return "var(--line)"
    return "var(--green)" if pct >= 70 else ("var(--amber)" if pct >= 50 else "var(--red)")


def bucket_pct(rec, name):
    v = rec["lifetime"].get(name)
    if not v or not v.get("n"):
        return None
    return round(v["c"] / v["n"] * 100)


def mmss(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def record_answer(rec, q, correct):
    b = q["b"]
    lt = rec["lifetime"].setdefault(b, {"c": 0, "n": 0})
    lt["n"] += 1
    if correct:
        lt["c"] += 1
        rec["missed"].pop(str(q["id"]), None)
    else:
        rec["missed"][str(q["id"])] = rec["missed"].get(str(q["id"]), 0) + 1


def grouped_missed(rec, only_bucket=None):
    groups = []
    for b in BUCKETS:
        if only_bucket and b != only_bucket:
            continue
        items = []
        for qid_str, misses in rec["missed"].items():
            q = QUESTIONS[int(qid_str)]
            if q["b"] != b:
                continue
            items.append({"q_html": q_html(q), "letter": LETTERS[q["a"]],
                          "answer": q["c"][q["a"]], "e": q["e"], "misses": misses,
                          "acs": q.get("acs")})
        if items:
            items.sort(key=lambda x: -x["misses"])
            groups.append({"name": b, "qs": items})
    return groups


# ---- Request lifecycle ------------------------------------------------------
@app.before_request
def _load_state():
    uid = request.cookies.get(COOKIE, "")
    if not _UID_RE.match(uid):
        uid = uuid4().hex
    g.uid = uid
    uname = session.get("user")
    g.user = read_users().get(uname) if uname else None
    g.owner = ("u:" + g.user["id"]) if g.user else ("d:" + uid)
    g.record = get_record(g.owner)
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    if request.method == "POST" and not secrets.compare_digest(
            request.form.get("_csrf", ""), session.get("_csrf", "")):
        abort(400)


@app.after_request
def _persist_cookie(resp):
    try:
        resp.set_cookie(COOKIE, g.uid, max_age=60 * 60 * 24 * 365,
                        samesite="Lax", httponly=True,
                        secure=(_SECURE_COOKIES or request.is_secure))
    except Exception:
        pass
    return resp


def soft_count(n):
    """Round a user-facing count down to a soft figure like '90+'.

    The bank is always growing, so displayed counts are shown softly rather than
    as exact, soon-to-be-stale numbers. User-specific counts (scores, missed
    items) are shown exactly and do not use this.
    """
    n = int(n)
    if n < 10:
        return str(n)
    step = 10 if n < 200 else 50
    return f"{(n // step) * step}+"


@app.context_processor
def _inject():
    return {"dark": g.record["prefs"].get("dark", False), "user": g.user,
            "icons": BUCKET_ICONS, "mastery": mastery_badge, "soft_count": soft_count,
            "acs_tasks": ACS_TASKS, "figures": FIGURES,
            "csrf_token": session.get("_csrf", "")}


# ---- Routes -----------------------------------------------------------------
@app.route("/")
def home():
    rec = g.record
    tot_c = sum(v["c"] for v in rec["lifetime"].values())
    tot_n = sum(v["n"] for v in rec["lifetime"].values())
    buckets = []
    for b in BUCKETS:
        pct = bucket_pct(rec, b)
        buckets.append({"name": b, "count": sum(1 for q in QUESTIONS if q["b"] == b),
                        "pct": pct, "color": color_for(pct)})
    return render_template("home.html",
                           lifetime_pct=(round(tot_c / tot_n * 100) if tot_n else None),
                           total_answered=tot_n, to_review=len(rec["missed"]),
                           buckets=buckets, exam_n=EXAM_N, exam_min=EXAM_MIN,
                           exam_scored=EXAM_SCORED,
                           exam_pass=EXAM_PASS)


@app.route("/practice")
def practice():
    bucket = request.args.get("bucket", "All")
    figonly = request.args.get("figures")
    if figonly:
        pool = [q for q in QUESTIONS if q.get("fig")]
        bucket = "All"
    else:
        pool = QUESTIONS if bucket == "All" else [q for q in QUESTIONS if q["b"] == bucket]
    if not pool:
        return redirect(url_for("home"))
    q = random.choice(pool)
    order = list(range(len(q["c"])))
    random.shuffle(order)
    return render_template("practice.html", answered=False, mode="practice",
                           drill_bucket=None, q={**q, "q_html": q_html(q)},
                           choices=shuffled(order, q), bucket=bucket, figmode=figonly)


@app.route("/drill")
def drill():
    """Serve missed questions, weighted toward the ones missed most often."""
    only = request.args.get("bucket")
    if only not in BUCKETS:
        only = None
    pool, weights = [], []
    for qid_str, misses in g.record["missed"].items():
        q = QUESTIONS[int(qid_str)]
        if only and q["b"] != only:
            continue
        pool.append(q)
        weights.append(misses)
    if not pool:
        return render_template("practice.html", drill_empty=True, mode="drill",
                               drill_bucket=only)
    q = random.choices(pool, weights=weights, k=1)[0]
    order = list(range(len(q["c"])))
    random.shuffle(order)
    return render_template("practice.html", answered=False, mode="drill",
                           drill_bucket=only, q={**q, "q_html": q_html(q)},
                           choices=shuffled(order, q), bucket=q["b"])


@app.route("/focus")
def focus():
    """Practice weighted toward the weakest topics; unseen topics get strong focus."""
    weights = []
    for b in BUCKETS:
        v = g.record["lifetime"].get(b)
        if v and v.get("n"):
            pct = v["c"] / v["n"] * 100
            weights.append(max(8.0, 100 - pct))
        else:
            weights.append(70.0)
    bucket = random.choices(BUCKETS, weights=weights, k=1)[0]
    pool = [q for q in QUESTIONS if q["b"] == bucket]
    q = random.choice(pool)
    order = list(range(len(q["c"])))
    random.shuffle(order)
    return render_template("practice.html", answered=False, mode="focus",
                           drill_bucket=None, q={**q, "q_html": q_html(q)},
                           choices=shuffled(order, q), bucket=q["b"])


@app.route("/learn")
def learn():
    """Flashcard-style study: read each question with its answer and rule, no quiz."""
    bucket = request.args.get("bucket")
    if bucket not in BUCKETS:
        bucket = BUCKETS[0]
    pool = [q for q in QUESTIONS if q["b"] == bucket]
    total = len(pool)
    try:
        n = int(request.args.get("n", 0))
    except (TypeError, ValueError):
        n = 0
    n = max(0, min(n, total - 1))
    q = pool[n]
    choices = [{"idx": i, "letter": LETTERS[i], "text": q["c"][i]} for i in range(len(q["c"]))]
    return render_template("learn.html", bucket=bucket, n=n, total=total,
                           q={**q, "q_html": q_html(q)}, choices=choices,
                           bucket_names=BUCKETS)


@app.route("/cheatsheet")
def cheatsheet():
    """A condensed, printable list of every distinct rule, grouped by topic."""
    sheet = []
    for b in BUCKETS:
        seen, rules = set(), []
        for q in QUESTIONS:
            if q["b"] != b:
                continue
            e = q["e"].strip()
            if e and e not in seen:
                seen.add(e)
                rules.append(e)
        rules.sort()
        sheet.append({"name": b, "rules": rules, "count": len(rules)})
    total = sum(s["count"] for s in sheet)
    return render_template("cheatsheet.html", sheet=sheet, total=total)


@app.route("/practice/answer", methods=["POST"])
def practice_answer():
    qid = int(request.form.get("qid", -1))
    bucket = request.form.get("bucket", "All")
    mode = request.form.get("mode", "practice")
    dbucket = request.form.get("dbucket") or None
    figmode = request.form.get("figures") or None
    chosen = int(request.form.get("choice", -1))
    if not (0 <= qid < len(QUESTIONS)):
        return redirect(url_for("home"))
    q = QUESTIONS[qid]
    correct = chosen == q["a"]
    record_answer(g.record, q, correct)
    save_record(g.owner, g.record)
    choices = [{"idx": i, "letter": LETTERS[i], "text": q["c"][i]} for i in range(len(q["c"]))]
    return render_template("practice.html", answered=True, mode=mode, drill_bucket=dbucket,
                           q={**q, "q_html": q_html(q)},
                           choices=choices, chosen=chosen, correct=correct, bucket=bucket,
                           figmode=figmode)


def _bucket_index():
    """Map each bucket to the list of question ids it contains."""
    idx = {}
    for i, q in enumerate(QUESTIONS):
        idx.setdefault(q["b"], []).append(i)
    return idx


def _apportion(total, weights):
    """Split `total` across buckets in proportion to `weights`.

    Uses the largest-remainder method so the parts always sum to `total`
    exactly, regardless of rounding.
    """
    s = sum(weights.values()) or 1
    raw = {b: total * w / s for b, w in weights.items()}
    out = {b: int(v) for b, v in raw.items()}
    remaining = total - sum(out.values())
    by_frac = sorted(weights, key=lambda b: raw[b] - out[b], reverse=True)
    for b in by_frac[:remaining]:
        out[b] += 1
    return out


@app.route("/exam/start")
def exam_start():
    idx = _bucket_index()
    targets = _apportion(EXAM_SCORED, EXAM_BLUEPRINT)
    scored, leftovers = [], []
    for b in BUCKETS:
        pool = list(idx.get(b, []))
        random.shuffle(pool)
        want = min(targets.get(b, 0), len(pool))
        scored.extend(pool[:want])
        leftovers.extend(pool[want:])
    # If caps/rounding left the scored set short, top up from any topic.
    random.shuffle(leftovers)
    if len(scored) < EXAM_SCORED:
        need = EXAM_SCORED - len(scored)
        scored.extend(leftovers[:need])
        leftovers = leftovers[need:]
    # The 5 experimental (unscored) questions come from any topic, so they are
    # indistinguishable from scored ones during the exam.
    experimental = leftovers[:EXAM_EXPERIMENTAL]
    qids = scored + experimental
    random.shuffle(qids)
    order = {}
    for qid in qids:
        o = list(range(len(QUESTIONS[qid]["c"])))
        random.shuffle(o)
        order[str(qid)] = o
    g.record["exam"] = {"qids": qids, "order": order, "answers": {}, "start": time.time(),
                        "experimental": experimental}
    save_record(g.owner, g.record)
    return redirect(url_for("exam_q", n=0))


@app.route("/exam/q/<int:n>")
def exam_q(n):
    exam = g.record.get("exam")
    if not exam:
        return redirect(url_for("exam_start"))
    remaining = EXAM_MIN * 60 - (time.time() - exam["start"])
    if remaining <= 0:
        return redirect(url_for("exam_submit"))
    total = len(exam["qids"])
    n = max(0, min(n, total - 1))
    qid = exam["qids"][n]
    q = QUESTIONS[qid]
    saved = exam["answers"].get(str(qid))
    answered_set = {i for i, qd in enumerate(exam["qids"]) if str(qd) in exam["answers"]}
    return render_template("exam.html", n=n, total=total, q={**q, "q_html": q_html(q)},
                           choices=shuffled(exam["order"][str(qid)], q),
                           saved=(int(saved) if saved is not None else -1),
                           answered_set=answered_set, remaining=int(remaining),
                           remaining_mmss=mmss(remaining))


@app.route("/exam/nav", methods=["POST"])
def exam_nav():
    exam = g.record.get("exam")
    if not exam:
        return redirect(url_for("home"))
    n = int(request.form.get("n", 0))
    choice = request.form.get("choice")
    if choice is not None and 0 <= n < len(exam["qids"]):
        exam["answers"][str(exam["qids"][n])] = int(choice)
    save_record(g.owner, g.record)
    if request.form.get("finish"):
        return redirect(url_for("exam_submit"))
    goto = int(request.form.get("goto", n))
    return redirect(url_for("exam_q", n=goto))


@app.route("/exam/submit")
def exam_submit():
    exam = g.record.get("exam")
    if not exam:
        return redirect(url_for("home"))
    qids = exam["qids"]
    experimental = set(exam.get("experimental", []))
    answers = exam["answers"]
    correct = 0
    total = 0
    per = {}
    missed_now = []
    for qid in qids:
        q = QUESTIONS[qid]
        ok = answers.get(str(qid)) == q["a"]
        record_answer(g.record, q, ok)
        if qid in experimental:
            continue
        total += 1
        p = per.setdefault(q["b"], {"c": 0, "n": 0})
        p["n"] += 1
        if ok:
            p["c"] += 1
            correct += 1
        else:
            missed_now.append(q)
    pct = round(correct / total * 100) if total else 0
    passed = pct >= EXAM_PASS
    elapsed = time.time() - exam["start"]
    mock_id = exam.get("mock")
    g.record["sessions"].append({"date": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                 "mode": ("mock" + str(mock_id)) if mock_id is not None else "exam",
                                 "pct": pct, "correct": correct,
                                 "total": total, "passed": passed})
    g.record["sessions"] = g.record["sessions"][-50:]
    g.record["exam"] = None
    save_record(g.owner, g.record)

    by_bucket = []
    for b in BUCKETS:
        if b in per:
            p = per[b]
            pp = round(p["c"] / p["n"] * 100)
            by_bucket.append({"name": b, "c": p["c"], "n": p["n"], "pct": pp,
                              "color": color_for(pp)})
    missed = []
    for b in BUCKETS:
        items = [{"q_html": q_html(q), "letter": LETTERS[q["a"]],
                  "answer": q["c"][q["a"]], "e": q["e"], "acs": q.get("acs")}
                 for q in missed_now if q["b"] == b]
        if items:
            missed.append({"name": b, "qs": items})
    # ACS tasks to study from this exam, mirroring the FAA Knowledge Test Report.
    acs_counts = {}
    for q in missed_now:
        code = q.get("acs")
        if code:
            acs_counts[code] = acs_counts.get(code, 0) + 1
    acs_summary = sorted(
        ({"code": c, "title": ACS_TASKS.get(c, c), "n": n}
         for c, n in acs_counts.items()),
        key=lambda x: (-x["n"], x["code"]))
    return render_template("exam_result.html", pct=pct, passed=passed, correct=correct,
                           total=total, time_used=mmss(elapsed), exam_pass=EXAM_PASS,
                           experimental=EXAM_EXPERIMENTAL,
                           pass_color=color_for(pct), by_bucket=by_bucket, missed=missed,
                           acs_summary=acs_summary, mock_id=mock_id,
                           mock_title=(MOCK_EXAMS[mock_id]["title"]
                                       if mock_id is not None and mock_id < len(MOCK_EXAMS) else None))


# ---- Mock exams: five fixed, distinct, repeatable full-length practice tests ----
def _build_mocks():
    """Assemble five fixed mock exams from the bank.

    Each mock mirrors the real test: EXAM_SCORED scored questions apportioned by
    EXAM_BLUEPRINT plus EXAM_EXPERIMENTAL unscored ones. A fixed seed keeps the
    sets stable and repeatable, and questions are drawn without repeat across
    mocks where the pool allows, so the five are largely distinct.
    """
    rng = random.Random(20260107)
    targets = _apportion(EXAM_SCORED, EXAM_BLUEPRINT)
    idx = _bucket_index()
    queues = {b: rng.sample(idx.get(b, []), len(idx.get(b, []))) for b in BUCKETS}
    allq = rng.sample(range(len(QUESTIONS)), len(QUESTIONS))
    mocks = []
    for m in range(5):
        used, scored = set(), []
        for b in BUCKETS:
            q, want, got = queues.get(b, []), targets.get(b, 0), 0
            while got < want and q:
                qid = q.pop(0)
                if qid not in used:
                    scored.append(qid); used.add(qid); got += 1
        i = 0
        while len(scored) < EXAM_SCORED and i < len(allq):
            qid = allq[i]; i += 1
            if qid not in used:
                scored.append(qid); used.add(qid)
        scored = scored[:EXAM_SCORED]
        experimental = []
        while len(experimental) < EXAM_EXPERIMENTAL and i < len(allq):
            qid = allq[i]; i += 1
            if qid not in used:
                experimental.append(qid); used.add(qid)
        qids = scored + experimental
        order = {str(qid): rng.sample(range(len(QUESTIONS[qid]["c"])),
                                      len(QUESTIONS[qid]["c"])) for qid in qids}
        mocks.append({"title": "Mock Exam " + str(m + 1), "qids": qids,
                      "experimental": experimental, "order": order})
    return mocks


MOCK_EXAMS = _build_mocks()


@app.route("/mocks")
def mocks():
    best = {}
    for sn in g.record.get("sessions", []):
        mode = sn.get("mode", "")
        if mode.startswith("mock") and mode[4:].isdigit():
            mid = int(mode[4:])
            if sn.get("pct", -1) > best.get(mid, -1):
                best[mid] = sn["pct"]
    items = [{"id": i, "title": MOCK_EXAMS[i]["title"], "best": best.get(i),
              "passed": best.get(i, -1) >= EXAM_PASS}
             for i in range(len(MOCK_EXAMS))]
    return render_template("mocks.html", mocks=items, exam_n=EXAM_N,
                           exam_scored=EXAM_SCORED, exam_min=EXAM_MIN, exam_pass=EXAM_PASS)


@app.route("/mock/<int:mid>/start")
def mock_start(mid):
    if mid < 0 or mid >= len(MOCK_EXAMS):
        return redirect(url_for("mocks"))
    mk = MOCK_EXAMS[mid]
    g.record["exam"] = {"qids": list(mk["qids"]),
                        "order": {k: list(v) for k, v in mk["order"].items()},
                        "answers": {}, "start": time.time(),
                        "experimental": list(mk["experimental"]), "mock": mid}
    save_record(g.owner, g.record)
    return redirect(url_for("exam_q", n=0))


@app.route("/review")
def review():
    rec = g.record
    active = request.args.get("bucket")
    if active not in BUCKETS:
        active = None
    lifetime = []
    for b in BUCKETS:
        v = rec["lifetime"].get(b)
        if v and v.get("n"):
            pp = round(v["c"] / v["n"] * 100)
            lifetime.append({"name": b, "c": v["c"], "n": v["n"], "pct": pp,
                             "color": color_for(pp)})
    # ACS tasks to review: distinct missed questions per FAA ACS task, the way
    # the FAA Knowledge Test Report lists the codes an applicant should study.
    acs_counts = {}
    for qid_str in rec["missed"]:
        q = QUESTIONS[int(qid_str)]
        if active and q["b"] != active:
            continue
        code = q.get("acs")
        if code:
            acs_counts[code] = acs_counts.get(code, 0) + 1
    acs_summary = sorted(
        ({"code": c, "title": ACS_TASKS.get(c, c), "n": n}
         for c, n in acs_counts.items()),
        key=lambda x: (-x["n"], x["code"]))
    return render_template("review.html", lifetime=lifetime,
                           missed=grouped_missed(rec, active),
                           acs_summary=acs_summary,
                           bucket_names=BUCKETS, active_bucket=active)


@app.route("/studysheet")
def studysheet():
    """A personalized, printable sheet of weak ACS tasks and the rules to study."""
    rec = g.record
    by_task = {}
    for qid_str, misses in rec["missed"].items():
        q = QUESTIONS[int(qid_str)]
        code = q.get("acs") or "Other"
        t = by_task.get(code)
        if t is None:
            t = by_task[code] = {"code": code, "title": ACS_TASKS.get(code, "Other"),
                                 "misses": 0, "qcount": 0, "rules": [], "_seen": set()}
        t["misses"] += misses
        t["qcount"] += 1
        e = q["e"].strip()
        if e and e not in t["_seen"]:
            t["_seen"].add(e)
            t["rules"].append(e)
    tasks = sorted(by_task.values(), key=lambda x: (-x["misses"], x["code"]))
    for t in tasks:
        t.pop("_seen", None)
    return render_template("studysheet.html", tasks=tasks,
                           total_missed=len(rec["missed"]),
                           generated=time.strftime("%b %d, %Y"))


def _nice_date(iso):
    try:
        return time.strftime("%b %d \u00b7 %H:%M", time.strptime(iso, "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, TypeError):
        return iso


@app.route("/history")
def history():
    exams = [s for s in g.record["sessions"] if s.get("mode") == "exam"]
    taken = len(exams)
    if not taken:
        return render_template("history.html", taken=0)
    best = max(s["pct"] for s in exams)
    last5 = exams[-5:]
    avg5 = round(sum(s["pct"] for s in last5) / len(last5))
    pass_rate = round(sum(1 for s in exams if s["passed"]) / taken * 100)
    last3 = exams[-3:]
    avg3 = round(sum(s["pct"] for s in last3) / len(last3))
    if avg3 >= 85 and exams[-1]["passed"]:
        verdict = {"emoji": "\U0001F7E2", "label": "Exam-ready", "cls": "m-strong",
                   "note": "Your recent scores clear the bar with margin. Keep drilling any weak topics and you are in good shape."}
    elif avg3 >= EXAM_PASS:
        verdict = {"emoji": "\U0001F7E1", "label": "On the cusp", "cls": "m-learn",
                   "note": "You are passing, but the margin is thin. Aim for 85%+ across a few exams for a comfortable cushion."}
    else:
        verdict = {"emoji": "\U0001F534", "label": "Keep studying", "cls": "m-focus",
                   "note": "Recent scores are below the " + str(EXAM_PASS) + "% passing line. Drill your missed questions, then retest."}
    recent = [{**s, "when": _nice_date(s.get("date", ""))} for s in reversed(exams)][:15]
    trend = exams[-12:]
    return render_template("history.html", taken=taken, best=best, avg5=avg5,
                           pass_rate=pass_rate, verdict=verdict, recent=recent,
                           trend=trend, exam_pass=EXAM_PASS)


def _safe_back():
    """Return the referring page only when GET is valid there, otherwise home.

    Prevents redirecting (via GET) back to a POST-only endpoint such as
    /practice/answer, which would raise 405 Method Not Allowed.
    """
    ref = request.referrer
    if ref:
        try:
            app.url_map.bind(urlparse(ref).netloc or "localhost").match(
                urlparse(ref).path, method="GET")
            return ref
        except Exception:
            pass
    return url_for("home")


@app.route("/theme/toggle")
def toggle_theme():
    g.record["prefs"]["dark"] = not g.record["prefs"].get("dark", False)
    save_record(g.owner, g.record)
    return redirect(_safe_back())


@app.route("/progress/reset", methods=["POST"])
def reset_progress():
    g.record = _fresh()
    save_record(g.owner, g.record)
    return redirect(url_for("home"))


@app.route("/progress/export")
def export_progress():
    payload = json.dumps({k: g.record[k] for k in ("lifetime", "missed", "sessions", "prefs")},
                         indent=2)
    return Response(payload, mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=part107-progress.json"})


@app.route("/api/health")
def api_health():
    return jsonify(status="ok", questions=len(QUESTIONS))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        err = validate_credentials(email, password)
        users = read_users()
        if not err and email.lower() in users:
            err = "An account with that email already exists."
        if err:
            return render_template("register.html", error=err, email=email)
        user_id = uuid4().hex
        users[email.lower()] = {"id": user_id, "email": email,
                                "pw_hash": generate_password_hash(password),
                                "created": time.strftime("%Y-%m-%dT%H:%M:%S")}
        write_users(users)
        session["user"] = email.lower()
        migrate_device_to_user(user_id)
        return redirect(url_for("home"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = read_users().get(email)
        if not user or not check_password_hash(user["pw_hash"], password):
            return render_template("login.html", error="Wrong email or password.",
                                   email=request.form.get("email", ""))
        session["user"] = email
        migrate_device_to_user(user["id"])
        return redirect(url_for("home"))
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))


if __name__ == "__main__":
    print("Part 107 Ground School running at http://127.0.0.1:8000")
    # Debug is off by default; set FLASK_DEBUG=1 for auto-reload and the debugger.
    debug = os.environ.get("FLASK_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")
    app.run(host="127.0.0.1", port=8000, debug=debug)
