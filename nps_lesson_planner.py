#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NPS International School Guwahati - Lesson Planner (offline, Termux)
====================================================================
One file. Python 3 standard library only. No internet needed.

  1. pkg install python -y
  2. termux-setup-storage            (once - lets PDFs be saved in your Downloads)
  3. cp ~/storage/downloads/nps_lesson_planner.py ~/     (copy this file into Termux)
  4. python nps_lesson_planner.py    (opens the app in your phone browser)

Next time, just run step 4.  Stop the app with CTRL+C.  Optional flags: --port 9000  --no-open

Formats reproduced exactly from the school documents:
  * Mathematics -> daily lesson card  ("File 2")
  * Science     -> monthly section + day-wise tables ("File 1")
"""
import os, re, sys, json, time, zlib, math, uuid, threading, subprocess, datetime, calendar, traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

APP_NAME = "NPS Lesson Planner"
SCHOOL_MATH = "NPS INTERNATIONAL SCHOOL GUWAHATI"        # exactly as in the Maths format
SCHOOL_SCI = "NPS INTERNATIONAL SCHOOL, GUWAHATI"        # exactly as in the Science format
SCHOOL_FOOT = "NPS International School Guwahati"
LBL_WRAP = "WRAP ACITVITY:"   # spelled exactly as in the original Maths format

HOME = os.path.expanduser("~")
APPDIR = os.path.join(HOME, ".nps_lesson_planner")
DB_PATH = os.path.join(APPDIR, "data.json")
_lock = threading.Lock()

# ------------------------------------------------------------------ dates
def parse_iso(s):
    return datetime.date(int(s[0:4]), int(s[5:7]), int(s[8:10]))

def dmy(d):
    return "%02d/%02d/%04d" % (d.day, d.month, d.year)

def session_for(d):
    y = d.year if d.month >= 4 else d.year - 1
    return "%d-%02d" % (y, (y + 1) % 100)

def month_label(d):
    return "%s %d" % (calendar.month_name[d.month], d.year)

def date_range(a, b):
    out, d = [], a
    while d <= b:
        out.append(d)
        d += datetime.timedelta(days=1)
    return out

# ------------------------------------------------------------------ storage
def default_db():
    return {"settings": {"teacher": "", "minutes": 40, "session": ""},
            "library": [], "holidays": [], "history": {"chapters": [], "topics": []}}

def db_load():
    with _lock:
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
            base = default_db()
            base.update(d)
            return base
        except Exception:
            return default_db()

def db_save(data):
    with _lock:
        os.makedirs(APPDIR, exist_ok=True)
        tmp = DB_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, DB_PATH)

def out_dirs():
    """Return (folder, is_shared_storage). Shared storage = visible to other Android apps."""
    for base in (os.path.join(HOME, "storage", "downloads"), "/storage/emulated/0/Download", "/sdcard/Download"):
        try:
            if os.path.isdir(base) and os.access(base, os.W_OK):
                d = os.path.join(base, "NPS_Lesson_Plans")
                os.makedirs(d, exist_ok=True)
                return d, True
        except Exception:
            pass
    d = os.path.join(HOME, "NPS_Lesson_Plans")
    os.makedirs(d, exist_ok=True)
    return d, False

def find_pdf(name):
    if not re.match(r"^[\w\-. ]+\.pdf$", name or ""):
        return None
    for base in (os.path.join(HOME, "storage", "downloads", "NPS_Lesson_Plans"),
                 "/storage/emulated/0/Download/NPS_Lesson_Plans", "/sdcard/Download/NPS_Lesson_Plans",
                 os.path.join(HOME, "NPS_Lesson_Plans")):
        p = os.path.join(base, name)
        if os.path.isfile(p):
            return p
    return None

# Helvetica / Helvetica-Bold advance widths (1/1000 em), cp1252 codes 32..255
WID_R = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584, 761, 556, 556, 222, 556, 333, 1000, 556, 556, 333, 1000, 667, 333, 1000, 556, 611, 556, 556, 222, 222, 333, 333, 350, 556, 1000, 333, 1000, 500, 333, 944, 556, 500, 667, 278, 333, 556, 556, 556, 556, 260, 556, 333, 737, 370, 556, 584, 333, 737, 333, 400, 584, 333, 333, 333, 556, 537, 278, 333, 333, 365, 556, 834, 834, 834, 611, 667, 667, 667, 667, 667, 667, 1000, 722, 667, 667, 667, 667, 278, 278, 278, 278, 722, 722, 778, 778, 778, 778, 778, 584, 778, 722, 722, 722, 722, 667, 667, 611, 556, 556, 556, 556, 556, 556, 889, 500, 556, 556, 556, 556, 278, 278, 278, 278, 556, 556, 556, 556, 556, 556, 556, 584, 611, 556, 556, 556, 556, 500, 556, 500]
WID_B = [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611, 975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556, 333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611, 611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584, 761, 556, 556, 278, 556, 500, 1000, 556, 556, 333, 1000, 667, 333, 1000, 556, 611, 556, 556, 278, 278, 500, 500, 350, 556, 1000, 333, 1000, 556, 333, 944, 556, 500, 667, 278, 333, 556, 556, 556, 556, 280, 556, 333, 737, 370, 556, 584, 333, 737, 333, 400, 584, 333, 333, 333, 611, 556, 278, 333, 333, 365, 556, 834, 834, 834, 611, 722, 722, 722, 722, 722, 722, 1000, 722, 667, 667, 667, 667, 278, 278, 278, 278, 722, 722, 778, 778, 778, 778, 778, 584, 778, 722, 722, 722, 722, 667, 667, 611, 556, 556, 556, 556, 556, 556, 889, 556, 556, 556, 556, 556, 278, 278, 278, 278, 611, 611, 611, 611, 611, 611, 611, 584, 611, 611, 611, 611, 611, 556, 611, 556]


# =====================================================================
#  OFFLINE AUTOFILL ENGINE
#  Rule-based: detects the kind of topic from keywords, then weaves the
#  chapter + topic into grade-appropriate objectives, activities, etc.
# =====================================================================
SDG = {1: "No Poverty", 2: "Zero Hunger", 3: "Good Health and Well-being", 4: "Quality Education",
       5: "Gender Equality", 6: "Clean Water and Sanitation", 7: "Affordable and Clean Energy",
       8: "Decent Work and Economic Growth", 9: "Industry, Innovation and Infrastructure",
       10: "Reduced Inequalities", 11: "Sustainable Cities and Communities",
       12: "Responsible Consumption and Production", 13: "Climate Action", 14: "Life Below Water",
       15: "Life on Land", 16: "Peace, Justice and Strong Institutions", 17: "Partnerships for the Goals"}

# keys ~ kind ~ hook ~ activity ~ real life ~ prior knowledge ~ interdisciplinary ~ SDGs
# key syntax:  word* = prefix match, !phrase = strong (weight 3)
MATH_KB = r"""
derivative*|differentiat*|integra*|limit|continuity|calculus|rate of change|maxima|minima|area under|differential equation~T~Ask how a speedometer can show the speed at one exact instant~Use tables and graphs to watch average change settle into instantaneous change, then practise the rules step by step~speed and acceleration, optimising cost or material, population growth~functions, graphs and simple limits~Physics (motion), Economics (marginal cost)~9:modelling for innovation
trigonometr*|sin|cos|tan|cot|sec|cosec|elevation|depression|height and distance*~T~Ask how the height of a tall tree or tower can be found without climbing it~Make a clinometer from a protractor, straw and thread, measure angles of elevation outdoors and calculate heights with trigonometric ratios~surveying land, architecture, aviation, astronomy~right-angled triangles and the Pythagoras theorem~Physics (waves), Geography (surveying)~9:infrastructure design,11
permutation*|combination*|binomial|factorial|counting principle|fundamental principle|arrangement*~T~Ask how many different 3-digit lock codes or line-ups of four friends are possible~List the possibilities with tree diagrams and cards first, then introduce the counting rules and formulae~passwords, seating plans, team selection, probability~multiplication and the idea of factors~Computer Science (passwords and codes)~
matri*|determinant*|vector*~T~Show a stock table of items in rows and columns and ask how two such tables could be added~Represent real tables of data as arrays and carry out each operation on small numerical examples before generalising~spreadsheets, computer graphics, inventory records, forces and velocities in physics~algebra and coordinates~Computer Science (spreadsheets, graphics), Physics (vectors)~
conic*|parabola|ellipse|hyperbola|slope|straight line*|three dimensional|3d geometry|linear programming~T~Show a satellite dish or a torch beam and ask which curve shapes the reflector~Use paper-folding and graph sketches (or GeoGebra) to generate the curves, then derive the standard equations step by step~satellite dishes, planetary orbits, bridge arches, optimisation in industry~coordinates and the distance formula~Physics (orbits and optics), Engineering design~9
coordinate*|cartesian|distance formula|section formula|ordered pair*|quadrant*|plot*|!graph of~T~Ask students to describe a classmate's seat using row and column numbers, like a map reference~Play a floor-grid game, then plot points and shapes on graph paper and find distances and mid-points~maps and GPS, seating plans, pixels on a screen, board games~the number line and integers~Geography (latitude and longitude), Computer Science (pixels)~
arithmetic progression*|geometric progression*|a.p|sequence*|series|nth term~P~Show a staircase or a pile of bricks and ask how the count changes row by row~Build patterns with matchsticks or counters, find the rule, write the nth term and test it~regular savings, seating in a stadium, instalments~number patterns and linear expressions~Economics (savings), Art (pattern designs)~1:planning savings
polynomial*|zero of*|zeroes|zeros|factoris*|factoriz*|quadratic*|discriminant|roots of|remainder theorem|factor theorem~A~Ask which expression describes the height of a ball thrown into the air~Use algebra tiles to factorise expressions and graph y = ax^2 + bx + c from a table of values to spot the zeroes~projectile paths, fencing and area problems, bridge arches, profit models~algebraic expressions, identities and factorisation~Physics (projectile motion), Economics (profit models)~
square root*|cube root*|perfect square*|perfect cube*|squares and*|cubes and*|exponent*|power*|index|indices|surd*|irrational*|rational number*|real number*|scientific notation|standard form|radical*~N~Tile a floor with square tiles and ask which numbers of tiles make a perfect square~Build squares with tiles or dot paper, spot the patterns, then generalise the rules with examples~area of square plots, very large and very small quantities such as the distance to the Sun~multiplication tables and basic operations~Science (large and small quantities), Computer Science (powers of 2)~
equation*|linear|variable*|expression*|algebra*|identit*|inequalit*|simultaneous|substitution|elimination|formula*|bodmas|order of operations|brackets~A~Play a think-of-a-number puzzle such as 'I think of a number, add 5 and get 12'~Use a pan-balance model (or a drawing) to form and solve equations, and translate word statements into algebraic equations~bills and budgets, age problems, speed-time-distance, recipes~arithmetic operations, patterns and the use of letters for numbers~Science (formulae), Economics (cost and revenue)~
percent*|profit|loss|discount*|selling price|cost price|interest|tax*|gst|commission|ratio*|proportion*|unitary|variation*|rate of~R~Show a '20% off' sale poster and ask how much would be saved on a Rs 500 item~Role-play a class shop with price tags, discounts and bills; model percentages on 10 x 10 grids and use the unitary method~sales and discounts, bank interest, GST bills, recipes and map scales~fractions, decimals and multiplication facts~Commerce and Economics, Financial literacy~1:financial awareness,8,12:wise consumer choices
probability|chance*|likely|likelihood|outcome*|random~D~Toss a coin ten times and ask students to predict how many heads will appear~Run experiments with coins, dice and spinners, record the outcomes and compare experimental with theoretical probability~weather forecasts, games, insurance, quality testing~fractions and data handling~Science (genetics), Economics (risk)~
statistic*|data|mean|median|mode|bar graph*|pie chart*|histogram*|frequency|tally|pictograph*|range|chart*|ogive*|class interval*|average*|graphs~D~Take a quick class survey, such as favourite Bihu food, and ask how to show the result clearly~Collect real data in class (heights, birth months, rainfall), organise it in a tally table, draw a bar graph, pictograph or pie chart and interpret it~weather and rainfall reports, sports scores, surveys, election results~counting, comparing numbers and reading tables~Social Science (census and rainfall data), Computer Science (spreadsheets)~13:reading climate data
set|venn*|union|intersection*|subset*|relation*|function*|domain~P~Group the class by two overlapping interests, such as cricket and football, and see who belongs to both~Use human Venn diagrams and cards to model sets; show relations and functions as arrow diagrams, ordered pairs and tables~databases, classifying things, spreadsheets, timetables~types of numbers and listing objects~Computer Science (databases), Science (classification)~
area*|perimeter*|circumference|volume*|surface area*|cuboid*|cube|cylinder*|cone*|sphere*|hemisphere*|frustum*|mensuration|capacity~M~Ask how much paint will cover a wall or how much water will fill a tank~Use grid paper and unit cubes to discover area and volume ideas, and unfold net models to see surface area~painting walls, tiling floors, filling water tanks, packing boxes~area and perimeter of simple shapes and units of measurement~Art and Craft, Architecture, Science (capacity and density)~6:water storage and use,11
triangle*|congruen*|similar*|pythagoras|pythagorean|basic proportionality|thales|criteria~G~Ask why bridges, roof frames and cranes are built from triangles~Cut straws or strips to build triangles, test which lengths close up, and verify properties by paper-folding or GeoGebra~bridges, roof trusses, ladders, scale models and maps~types of triangles and the angle-sum property~Art (design), Engineering and Technology, Physics (forces)~9,11
circle*|chord*|tangent*|arc|sector*|segment*|radius|diameter|secant*~G~Roll a coin or a bicycle wheel and ask what makes a circle special~Draw circles with a compass and a string; measure radius, chords and tangents by folding and measuring~wheels, clocks, coins, round tables, ripples on water~radius, diameter and the use of a compass~Physics (circular motion), Art (mandala designs)~
quadrilateral*|parallelogram*|rhombus|rectangle*|trapezium|trapezoid*|kite*|polygon*|mid-point theorem|midpoint theorem~G~Let students spot and sort different four-sided shapes around the classroom~Use paper cut-outs and geoboards to explore sides, angles and diagonals, then sort the shapes on a Venn diagram~windows, floor tiles, kites, bridges and buildings~triangles and the angle-sum property~Art and Craft, Architecture~11
symmetr*|reflection*|rotation*|translation*|transformation*|tessellation*|shape*|2d|3d|solid*|face*|vertices|net|geometry~G~Fold a paper butterfly or a leaf and ask whether both halves match~Use paper folding and mirrors to find lines of symmetry; build solids from nets and count faces, edges and vertices~logos, rangoli, packaging boxes, buildings, traditional Assamese motifs such as the japi and gamosa borders~recognising common shapes~Art and Craft, Science (symmetry in nature)~
construction*|construct|compass|protractor|ruler~G~Ask whether an exact angle can be drawn without using a protractor~Demonstrate each construction step by step with compass and ruler, then let students construct and check by measuring~technical drawing, carpentry, map making and design~use of a ruler, compass and protractor~Art (geometric designs), Technology~
angle*|line|line segment*|ray|parallel|transversal|intersecting|perpendicular|bisector*|point|axiom*|!euclid's geometry~G~Open and close a pair of scissors or a door and ask what changes~Make angles with paper strips and a paper protractor; measure, classify and verify angle pairs by tracing~scissors, clock hands, road crossings, ladders against a wall~ideas of point, line and turn~Art (perspective drawing), Physical Education (body angles)~
factor*|multiple*|prime*|composite*|hcf|lcm|gcd|divisib*|euclid*|fundamental theorem*~N~Arrange 12 counters into equal rows and ask in how many different ways it can be done~Use factor rainbows and the Sieve of Eratosthenes chart, then find HCF and LCM by listing and by prime factorisation~scheduling repeating events, making equal packs or groups, tiling a floor~multiplication tables and divisibility rules~Computer Science (primes in codes), Music (rhythm cycles)~
integer*|negative*|positive*|number line~N~Ask what a temperature of -2 degrees, or a lift going below the ground floor, means~Walk the number line on the floor and use two-colour counters to model adding and subtracting integers~temperature, lift floors, bank credit and debit, sea level~whole numbers and the number line~Geography (altitude and temperature), Commerce~
fraction*|mixed number*|improper|proper~N~Fold a paper strip or a roti into equal parts and ask what part is shaded~Fold and shade paper strips to build, compare and order fractions and label numerators and denominators~sharing food equally, recipes, measuring cloth~equal sharing and division facts~Home Science (recipes), Art (colour patterns)~2:fair sharing of food
decimal*~N~Show price tags such as Rs 24.50 and ask what the digits after the point mean~Shade tenths and hundredths on 10 x 10 grids, then compare and order decimals on a number line~money, measuring length and weight, race timings~fractions with denominators 10 and 100~Physical Education (race timings), Commerce~
place value*|number name*|expanded form|large number*|big number*|indian system|international system|numbers up to|digit*|abacus~N~Show a large number on a place-value chart and ask which digit is worth the most~Build numbers with bead and digit cards on a place-value chart or abacus and write them in expanded form and in words~reading prices, population figures and distances~reading and writing smaller numbers~Social Science (population data), English (number names)~
addition|add|subtract*|multipl*|divi*|product*|quotient*|sum|difference|times table*|tables|carry|borrow|regroup*|operation*|estimat*~N~Play 'class shop': 'I have 3 pencils and buy 4 more, how many now?'~Model the operation with counters, ten-frames or number-line jumps, then record it as an equation or a column method~shopping bills, change, game scores, sharing sweets equally~counting and place value~EVS (counting things around us), Art and Craft~
time|clock*|calendar*|money|rupee*|paise|coin*|note*|currency|speed|distance|measure*|length|metre*|centimetre*|kilometre*|weight|gram*|kilogram*|litre*|millilitre*|unit*|conversion*|temperature~M~Ask students to estimate the length of their desk in handspans and then check with a ruler~Measure with rulers, balances and measuring jars; estimate first, then measure, record and convert units~cooking, travelling, shopping, sports~comparing and counting objects~EVS or Science (measuring), Physical Education~
pattern*|rangoli|tiling~P~Show a rangoli or a gamosa border and ask what repeats~Create and extend number and shape patterns with beads and cards and state the rule in words and symbols~rangoli, gamosa and mekhela border designs, calendars, tiling~counting in twos, fives and tens~Art and Craft, Science (patterns in nature)~
number*|count*|compar*|order*|greater|smaller|more than|less than|zero|tens|ones|hundreds|skip counting~N~Count the steps from the school gate to the classroom door together~Count and group real objects (stones, sticks, bundles of tens), compare with number cards and write the numerals~counting steps, money, birthdays, house numbers~counting objects up to 20~EVS, Art and Craft, English (number words)~
puzzle*|riddle*|word problem*|story sum*|problem solving|logic*|reasoning|mental math*|vedic|magic square*~P~Start with a riddle such as 'I am between 20 and 30 and I am a multiple of 7'~Set up solve-the-puzzle stations; students write their own word problems and swap them with a partner~everyday decisions, games, budgeting~the four operations~English (comprehension), Computer Science (logic)~
"""

SCI_KB = r"""
!photosynth*|chlorophyll|stomata|transpir*|leaf|leaves~B~Show a fresh green leaf next to a pale, yellowing one and ask why they look different~Test a leaf for starch with iodine and use a covered-leaf or variegated-leaf set-up to show that light and chlorophyll are needed; observe stomata in a leaf peel under a microscope~growing food, the oxygen we breathe, why trees matter in cities~parts of a plant and the need for sunlight~Geography (crops and climate), Art (leaf printing)~2:food production,13:trees and carbon dioxide,15
cell*|tissue*|organelle*|nucleus|cytoplasm|microscope*|mitosis|meiosis|chromosome*|membrane~B~Show an onion peel under a microscope, or a projected image, and ask what students see~Prepare a temporary onion-peel slide (or use microscope images), draw and label cell parts and compare plant and animal cells using a model~how the body grows and heals, medical tests and diagnosis~living and non-living things as units of structure~Art (making cell models), Health Education~3
plant*|root*|stem*|flower*|seed*|germinat*|fruit*|pollinat*|tropism*|vegetative|shoot~B~Pass around a flower or a seed and ask which parts students can spot and name~Dissect a flower and label its parts; germinate moong seeds on wet cotton and record the growth every day~farming, kitchen gardens, tea and bamboo in Assam, food and medicine from plants~parts of a plant~Art (botanical drawing), Agriculture and EVS~2,15
!nutri*|food|!digest*|diet*|vitamin*|mineral*|protein*|carbohydrate*|fats|malnutrition|deficiency|teeth|stomach|intestine*|alimentary~B~Ask students to list the items in their tiffin and the nutrient each one gives~Run simple food tests (iodine for starch, paper test for fats) or classify foods by nutrient on a chart, and build a balanced-diet plate model~choosing a healthy tiffin, preventing malnutrition, local food such as rice, fish and leafy greens~food groups and sources of food~Home Science, Health and Physical Education~2:good nutrition,3
!respirat*|breath*|lung*|diaphragm|gaseous exchange|oxygen|anaerobic|fermentation|aerobic~B~Ask students to hold their breath for a few seconds and describe how they feel when they breathe again~Count the breathing rate at rest and after exercise; model the lungs with a bottle, balloons and a rubber sheet; show carbon dioxide in exhaled air with lime water~exercise, asthma and air pollution, yoga and pranayama~organs of the body and the need for oxygen~Physical Education (exercise), Health Education~3,13
!circulat*|heart|blood|artery|arteries|vein*|pulse|xylem|phloem|excret*|kidney*|urine|sweat*|transport~B~Ask students to feel their pulse at rest and again after 20 jumps~Measure pulse rate in an investigation, model circulation with a flow chart and tubes, and show water rising in a celery stem placed in coloured water~heart health, blood donation, dialysis, exercise and fitness~organs and their functions~Physical Education (fitness), Health Education~3
!reproduc*|puberty|adolescen*|menstru*|fertilis*|fertiliz*|embryo*|metamorphosis|life cycle*|asexual|sexual|gamete*|zygote~B~Show pictures of a tadpole, a froglet and a frog and ask what students notice about the changes~Sort picture cards of life cycles (butterfly, frog, human), use slides or videos for budding in yeast, and hold an age-appropriate, respectful discussion with a question box~growth of animals and plants, family and adolescent health and hygiene~growth and change in living things~Health and Physical Education, EVS~3,5:equal access to health education
heredity|genetic*|mendel*|inherit*|trait*|variation*|dna|gene|evolution*|natural selection|fossil*|speciation~B~Compare traits such as rolling the tongue or attached earlobes across the class~Survey class traits with tally marks and a graph, model Mendel's pea crosses with two-coloured beads and build an evolution timeline chart~family resemblance, improving crops, medical genetics, conservation of species~reproduction and variation~Mathematics (probability and data), History (origin of humans)~3,15
ecosystem*|!food chain*|!food web*|ecolog*|biodiversity|habitat*|adaptation*|producer*|consumer*|decomposer*|biosphere|wildlife|forest*|species|endangered|biogeochemical~B~Show pictures of Kaziranga's animals and ask who eats whom~Build a food chain or web with picture cards and yarn, remove one organism to see the effect, and record living things on a walk in the school garden~Kaziranga's one-horned rhino, the birds of Deepor Beel, protecting local forests and wetlands~plants and animals and what they eat~Geography (biomes), Social Science (conservation)~14,15,13
microorganism*|microbe*|bacteria|virus*|fung*|disease*|vaccin*|immun*|pathogen*|antibiotic*|germ*|communicable|infect*|hygiene|sanitation~B~Ask what happens to a slice of bread left in a damp place for a week~Observe bread or fruit mould with a hand lens, show yeast acting on sugar, role-play how diseases spread and are prevented, and chart useful and harmful microbes~vaccination drives, hand-washing, food preservation, making curd and bread~cleanliness habits and living things~Health and Physical Education, Home Science~3,6:hygiene and clean water
animal*|insect*|bird*|fish|amphibian*|mammal*|reptile*|vertebrate*|invertebrate*|classification|kingdom*|taxonomy|skeleton*|bone*|joint*|muscle*|locomotion|movement*|sense organ*|nervous|brain|reflex|hormone*|endocrine|coordination|eye|ear~B~Show pictures of different animals and ask students to group them in as many ways as they can~Play a sorting game with picture cards and a simple dichotomous key, model joints with cardboard and string, and test reaction time with a falling ruler~pets and wildlife, safe play, how the body senses and responds~common animals and their features~Mathematics (data and graphs), Art (sketching)~3,15
acid*|base*|alkali*|salt*|ph|indicator*|neutralis*|neutraliz*|litmus|antacid*|soap*|detergent*|baking soda|crystallisation~C~Dip litmus paper into lemon juice and into a soap solution and ask what students notice~Test household substances (lemon, vinegar, soap, baking soda) with litmus, turmeric and red-cabbage indicator, sort them as acids, bases or neutral and show neutralisation with an antacid. Remind students never to taste chemicals~antacids for acidity, treating soil, toothpaste, cleaning at home~taste and feel of common substances~Home Science, Health (acidity)~3,12
metal*|nonmetal*|non-metal*|alloy*|reactivity|ore|extraction|rust*|corrosion|ionic|malleab*|ductil*|sonorous|lustre|luster~C~Tap a copper wire, a piece of coal and a steel spoon and compare their sound, shine and feel~Compare the physical properties of metals and non-metals through hands-on tests (conductivity circuit, hammering, shine) and set up a rusting experiment with iron nails in different conditions~cookware, electrical wires, jewellery, preventing rust on gates and bridges~materials around us~Social Science (mining and industries), Technology~9,12:recycling metals
carbon*|organic|hydrocarbon*|alkane*|alkene*|alkyne*|functional group*|ethanol|ethanoic|esterification|saponification|homologous|coal|petroleum|polymer*|plastic*|synthetic*|nylon|polythene~C~Burn a piece of paper and a piece of coal (teacher only) and ask what is left behind~Build models of simple carbon compounds with clay balls and sticks, sort everyday items as natural or synthetic, and let the teacher demonstrate burning tests safely~fuels, plastics, medicines, soaps, clothing fibres~elements and compounds~Environmental Studies (plastic waste), Technology~12:reducing plastic use,14
!fibre to fabric*|fibre*|fiber*|fabric*|cotton|jute|wool*|silk*|yarn*|spinning|weaving|muga|dyeing~C~Compare the threads of a gamosa and a woollen sweater and ask how they differ~Examine fabrics with a hand lens, untwist threads, sort fibres as natural or synthetic and twist cotton into yarn~Assam's Muga and Eri silk, weaving at Sualkuchi, choosing cotton clothes in summer~clothes we wear and the materials they are made of~Social Science (Assamese handloom economy), Art and Craft~8:livelihoods of weavers,12
chemical reaction*|equation*|balanc*|combination reaction*|decomposition|displacement|redox|oxidation|reduction|exothermic|endothermic|precipitat*|reactant*|chemical change*~C~Drop an effervescent tablet into water and ask what signs of change students can see~Demonstrate vinegar with baking soda and an iron nail in copper sulphate solution, record observations and write word equations, then balanced equations~cooking, rusting, burning fuels, digestion, batteries~physical and chemical changes~Mathematics (balancing), Technology~12,13
atom*|molecule*|element*|compound*|periodic*|valenc*|electron*|proton*|neutron*|isotope*|bohr|bonding|bond*|mole concept|avogadro|chemical formula*|radioactiv*~C~Ask what would happen if a piece of chalk were cut again and again into smaller pieces~Build models with beads, clay or ball-and-stick kits, sort element cards on a periodic table chart and draw electron arrangements~everyday materials such as salt, water and air, medical imaging, energy~matter and its states~Mathematics (patterns and ratios), History of Science~
matter|state*|solid*|liquid*|gas*|melting|boiling|evaporat*|condens*|sublimation|particle*|diffusion|!latent heat|density|mixture*|solution*|suspension*|colloid*|separat*|filtration|distillation|chromatograph*|sieving|solvent*|solute*|pure|impurit*|physical change*|material*~C~Ask why a puddle disappears on a sunny day~Run separation stations (filtration, evaporation, sieving, magnet, chromatography with ink) and record the temperature of ice and water as it is heated~making tea or salt, purifying water, drying clothes, cooking~solids, liquids and gases around us~Mathematics (graphs), Home Science~6,12
water*|rain|drinking|purif*|river*|brahmaputra|flood*|dam|irrigation|groundwater|water cycle*~E~Ask where the water in our taps comes from and let students draw its journey~Model the water cycle in a sealed bag, compare muddy, filtered and tap water with a sand-and-gravel filter and discuss rainwater harvesting~Brahmaputra floods and monsoon rains, safe drinking water, rainwater harvesting in Guwahati~the states of water~Geography (rivers and rainfall), Social Science (managing water)~6,13,14
air|wind|atmosphere|pollut*|ozone|greenhouse|global warming|climate*|waste*|recycl*|sustainab*|garbage|carbon footprint|natural resource*|fossil fuel*|renewable~E~Show a white cloth that was kept outdoors for a day and ask what has settled on it~Collect dust on a white cloth or sticky cards, hold a waste-segregation drive and make carbon-footprint pledge posters~Guwahati's traffic and air quality, plastic waste, waste segregation at home~air all around us~Social Science (environment), Art (poster making)~11,12,13
soil*|erosion|agricultur*|crop*|manure|fertilis*|fertiliz*|pesticide*|farming|harvest*|sowing|weed*|animal husbandry|poultry|fisheries|apiculture|!food production~E~Pass around different soil samples and ask how they differ in colour, feel and water-holding~Compare soil types with percolation and water-holding tests, show erosion on a slope with and without plant cover and chart the crop seasons~tea gardens, rice farming in Assam, kitchen gardens, composting~the need of plants for soil, water and sunlight~Geography (soil types), Economics (agriculture)~2,15
weather*|cyclone*|monsoon*|earthquake*|tsunami*|volcano*|disaster*|hazard*|seismic~E~Ask students to describe today's weather and how it changed since yesterday~Record daily temperature and rainfall on a class weather chart, use a shake-table model with blocks to show why buildings in earthquake-prone areas need strong design and discuss safety drills~monsoon floods in Assam, earthquakes in the North-East, safety drills at school~seasons and weather words~Geography, Social Science (disaster management)~11,13
moon|sun|solar system*|planet*|star|constellation*|universe|galax*|satellite*|eclipse*|tide*|night sky|day and night|season*|rotation|revolution|orbit*|astronom*|space~E~Ask why the Moon seems to change its shape from night to night~Use a torch and balls to model the Sun, Earth and Moon for phases and eclipses, make a scale model of the solar system with fruits or balls and use a night-sky chart~festivals and calendars based on the Moon, weather and communication satellites, ISRO missions~day and night and the Sun and Moon~Geography (seasons), Mathematics (scale and ratio), Social Science (calendars)~9,13
rock*|mineral*|crust|mantle|!layers of the earth|!interior of the earth|plate*|landform*|geolog*~E~Pass around rock samples and ask what students notice about colour, texture and weight~Observe and sort rock samples with a hand lens, show the folding of layers with layered clay and build a model of the layers of the Earth~building stones, minerals and mining, the Shillong Plateau~land, water and the surface of the Earth~Geography, Social Science~12,15
motion|speed|velocity|acceleration|distance|displacement|uniform|equations of motion|kinematics|measurement*|time period|pendulum|rectilinear|circular motion~P~Ask students to walk across the room slowly and then quickly and say what changed~Time a rolling trolley or ball over marked distances, plot a distance-time graph and count pendulum swings with a stopwatch~vehicle speed limits, sports races, trains and buses~distance, time and their units~Mathematics (graphs and ratios), Physical Education (athletics)~3,11:road safety
force*|friction|inertia|newton*|momentum|laws of motion|push|pull|balanced|unbalanced|impulse|collision*|recoil~P~Pull a sheet quickly from under a light object and ask why the object stays in place~Try push-and-pull trials, measure friction on different surfaces with a spring balance, run coin-and-card inertia demos and roll marbles into each other~seat belts, brakes, football, walking on slippery roads~motion and rest~Physical Education (sports), Mathematics (calculation)~3,11:road safety
pressure*|buoyan*|archimedes|float*|sink*|thrust|!density|atmospheric*|fluid*|hydraulic|upthrust|barometer~P~Ask why a needle sinks but a huge ship floats~Test floating and sinking with different objects, show Archimedes' principle with an overflow can and press different faces of a block into sand to compare pressure~ships and submarines, school-bag straps, injections, dams~weight, volume and measurement~Geography (oceans), Mathematics (units)~9,14
gravit*|free fall|weight|mass|kepler*|escape velocity~P~Drop a stone and a sheet of paper together and ask what pulls them down~Drop objects of different mass from the same height, weigh objects on a spring balance and compare Earth and Moon data~falling rain, space missions, weight on the Moon~force and motion~Social Science (ISRO missions), Mathematics (using formulae)~9
work|energy|power|kinetic|potential|conservation of energy|machine*|lever*|pulley*|inclined plane*|efficiency|!simple machine*~P~Ask whether lifting a book to a table or running up the stairs needs more energy~Investigate levers, pulleys and an inclined plane with a spring balance and turn potential energy into kinetic energy with a ball on a ramp~see-saws, crowbars, scissors, hydroelectric power, energy from food~force and motion~Physical Education, Mathematics (work = force x displacement)~7,13
!reflection*|mirror*|periscope|kaleidoscope|image*|incident*~P~Ask students to look at their face in a steel spoon and in a flat mirror and compare what they see~Use a torch, a plane mirror and a protractor on paper to measure the angles of incidence and reflection, locate an image with pins and build a simple periscope from a carton and two mirrors~mirrors in vehicles and at home, periscopes, kaleidoscopes, a dentist's mirror~light travelling in straight lines and the formation of shadows~Art (symmetry), Mathematics (angles)~3,7
refraction|lens*|!refractive index|!total internal reflection|bending of light|apparent depth|spectacle*~P~Place a coin in an empty bowl, step back until it just disappears and then add water~Show the bending of light with a pencil in water, trace rays through a glass slab on paper and compare convex and concave lenses by focusing sunlight or a candle image on a screen~spectacles, cameras, magnifying glasses, microscopes, optical fibres~reflection of light and the idea of a ray~Mathematics (angles), Technology~3:eye care,9
dispersion|prism*|spectrum|rainbow|colour*|color*|!white light~P~Hold a CD or a glass prism in sunlight and ask which colours students see on the wall~Split white light with a prism or a CD, recombine the colours with a Newton's disc and make a rainbow with a garden spray and sunlight~rainbows, sunsets, coloured stage lights, soap bubbles~white light and the colours around us~Art (colour mixing), Geography (atmosphere)~7
light|shadow*|optic*|pinhole|luminous|transparent|opaque|translucent|!human eye|!defects of vision~P~Make hand shadows on the wall and ask how they change as the light source moves~Use a torch and comb or a ray box to show that light travels in straight lines, make a pinhole camera and sort objects as transparent, translucent or opaque~mirrors, spectacles, cameras, rainbows, periscopes, optical fibres~everyday shadows and sources of light~Art (colour and perspective), Mathematics (angles)~3:eye care,7
sound*|vibrat*|echo*|pitch|loudness|amplitude|frequency|wave*|noise|ultrasound|sonar|musical instrument*|hearing|reverberation|decibel*~P~Ask students to hum with a hand on the throat and describe what they feel~Make a rubber-band guitar, touch a vibrating tuning fork to water, use a string telephone and vibrate a ruler to link vibration with sound, pitch and loudness~music, echoes in halls and valleys, ultrasound scans, noise pollution~everyday sounds and their sources~Music, Mathematics (frequency)~3:noise and health,11
heat*|temperature|thermometer*|conduction|convection|radiation|expansion|calorimetry|specific heat|thermal|!latent heat|hot|cold~P~Touch a metal spoon and a wooden spoon left in the sun and ask which feels hotter and why~Record water temperature over time, test conduction with wax-dotted rods, show convection with a coloured crystal in water and compare insulating materials~cooking vessels, thermos flasks, woollen clothes, sea breeze~hot and cold objects and the thermometer~Home Science (cooking), Geography (winds)~7,13
electric*|circuit*|battery|batteries|bulb*|resistance|ohm*|voltage|current|conductor*|insulator*|fuse*|switch*|static|charge*|lightning|earthing|!electric cell~P~Ask how pressing a switch makes a bulb glow instantly~Build simple circuits with a cell, bulb, switch and wires, test conductors and insulators, compare series and parallel arrangements and, for senior classes, verify Ohm's law with ammeter and voltmeter readings. Use cells only, never mains electricity~home wiring and safety, torch and mobile batteries, saving electricity, lightning safety~sources of electricity and the parts of a bulb and a cell~Mathematics (graphs and ratios), Technology~7,12:saving electricity
magnet*|compass*|pole|poles|electromagnet*|field line*|solenoid|!magnetic field*~P~Bring a magnet near pins, paper and a coin and ask what it picks up~Test magnetic and non-magnetic materials, show field lines with iron filings and make a simple compass and an electromagnet with a nail, wire and cell~compasses for direction, fridge magnets, electric bells, cranes, maglev trains~materials around us~Geography (directions), Technology~9
"""

def _parse_sdg(s):
    out = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        n, _, why = part.partition(":")
        try:
            out.append((int(n), why.strip()))
        except ValueError:
            pass
    return out

def _load_kb(raw):
    kb = []
    for line in raw.strip().split("\n"):
        f = [x.strip() for x in line.split("~")]
        if len(f) != 8:
            continue
        keys = []
        for k in f[0].split("|"):
            w = 1
            if k.startswith("!"):
                w, k = 3, k[1:]
            if k.endswith("*"):
                rx = r"\b" + re.escape(k[:-1]) + r"\w*"
            else:
                rx = r"\b" + re.escape(k) + r"(?:s|es)?\b"
            keys.append((re.compile(rx, re.I), w))
        kb.append({"keys": keys, "kind": f[1], "hook": f[2], "act": f[3], "real": f[4],
                   "prior": f[5], "inter": f[6], "sdg": _parse_sdg(f[7])})
    return kb

KB = {"math": _load_kb(MATH_KB), "sci": _load_kb(SCI_KB)}

GENERIC = {
    "math": {"kind": "X", "hook": "Pose a real-life question that can only be answered by understanding the topic",
             "act": "Explore the idea with concrete materials, diagrams and examples, moving from objects to pictures to symbols",
             "real": "everyday situations at home, in the market and in sports", "prior": "what was learnt in the previous lesson",
             "inter": "Science, Social Science and Art", "sdg": []},
    "sci": {"kind": "X", "hook": "Show an object, picture or short demonstration related to the topic and ask 'What do you notice? What do you wonder?'",
            "act": "Carry out a simple hands-on activity or teacher demonstration, observe carefully, record findings and discuss what they show",
            "real": "everyday situations at home and in our surroundings", "prior": "what was learnt in the previous lesson",
            "inter": "Mathematics, Geography and Health Education", "sdg": []},
}

def analyze(subject, chapter, topic):
    """Pick the knowledge-base entry that best matches the topic (then the chapter)."""
    for text in (topic, chapter):
        best, bs = None, 0
        for e in KB[subject]:
            s = sum(w for rx, w in e["keys"] if rx.search(text or ""))
            if s > bs:
                best, bs = e, s
        if best:
            return best
    return GENERIC[subject]

# ------------------------------------------------------------------ helpers
def clean(s):
    return re.sub(r"\s+", " ", (s or "").replace("\u00a0", " ")).strip()

def split_topics(text):
    seen, out = set(), []
    for t in re.split(r"[\n;]+", text or ""):
        t = clean(t).strip(" .")
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out

def speak(t):
    parts = [x.strip() for x in t.split(";") if x.strip()]
    if len(parts) <= 1:
        return t
    return ", ".join(parts[:-1]) + " and " + parts[-1]

def Q(t):
    return "\u2018%s\u2019" % speak(t)

def cap(s):
    return s[:1].upper() + s[1:] if s else s

def sent(s):
    s = clean(s)
    if not s:
        return s
    s = cap(s)
    return s if s[-1] in ".!?" else s + "."

def pick(options, *seed):
    h = zlib.crc32("|".join(str(x) for x in seed).encode("utf-8"))
    return options[h % len(options)]

def band(grade):
    g = int(grade)
    return 0 if g <= 2 else 1 if g <= 5 else 2 if g <= 8 else 3 if g <= 10 else 4

def split_minutes(total, weights):
    """Share `total` minutes across weights (percent) using largest remainder."""
    total = max(total, len(weights))
    raw = [total * w / float(sum(weights)) for w in weights]
    base = [max(1, int(r)) for r in raw]
    diff = total - sum(base)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - int(raw[i]), reverse=(diff > 0))
    i = 0
    while diff != 0 and order:
        j = order[i % len(order)]
        if diff > 0:
            base[j] += 1; diff -= 1
        elif base[j] > 1:
            base[j] -= 1; diff += 1
        i += 1
        if i > 500:
            break
    return base

def sdg_text(entry_sdgs, extra_reason="inclusive, activity-based learning"):
    parts = ["SDG 4 \u2013 Quality Education (%s)" % extra_reason]
    for n, why in entry_sdgs:
        if n == 4 or len(parts) >= 3 or n not in SDG:
            continue
        parts.append("SDG %d \u2013 %s%s" % (n, SDG[n], " (%s)" % why if why else ""))
    return "; ".join(parts)

PHASE_LABEL = {"full": "", "intro": "Introduction and concept building", "build": "Concept consolidation with examples",
               "practice": "Guided and independent practice", "apply": "Application and problem solving",
               "revise": "Revision and assessment"}

def phase_seq(n, fin):
    if n <= 1:
        return ["full"]
    if n == 2:
        return ["intro", "practice"]
    cyc = ["build", "practice", "apply", "practice"]
    if fin:
        mid = ["practice"] if n == 3 else [cyc[i % 4] for i in range(n - 2)]
        return ["intro"] + mid + ["revise"]
    mid = ["build", "practice"] if n == 3 else [cyc[i % 4] for i in range(n - 1)]
    return ["intro"] + mid

def plan_days(topics, nd):
    """Spread topics (and learning phases) across nd teaching days -> [(topic, phase)]."""
    if nd <= 0:
        return []
    T = topics or ["Selected topic"]
    if len(T) == 1:
        return [(T[0], p) for p in phase_seq(nd, True)]
    if len(T) >= nd:
        out = []
        for i in range(nd):
            a, b = i * len(T) // nd, (i + 1) * len(T) // nd
            out.append(("; ".join(T[a:b]), "full"))
        return out
    rev = 1 if nd >= len(T) + 1 and nd >= 4 else 0
    avail = nd - rev
    base, extra = divmod(avail, len(T))
    out = []
    for i, t in enumerate(T):
        n = base + (1 if i < extra else 0)
        out += [(t, p) for p in phase_seq(n, False)]
    if rev:
        out.append(("; ".join(T), "revise"))
    return out

def topic_line(topic, phase):
    lab = PHASE_LABEL.get(phase, "")
    return "%s \u2013 %s" % (topic, lab) if lab else topic

# ------------------------------------------------------------------ MATHEMATICS daily plan builder
M_SK = {"N": "perform the related operations accurately and check their answers by estimation",
        "A": "form, simplify and solve statements related to {T} with correct steps",
        "G": "draw, measure and reason about the figures involved in {T} and give simple justifications",
        "M": "choose the correct formula or unit and calculate the required measurements for {T}",
        "D": "collect, organise, represent and interpret data or outcomes related to {T}",
        "R": "set up and solve problems on {T} using ratios, percentages or the unitary method",
        "T": "apply the formulae and procedures of {T} to solve standard problems step by step",
        "P": "recognise the pattern or rule in {T} and use it to solve problems",
        "X": "apply the ideas of {T} to solve problems accurately"}
M_PH_O2 = {"practice": "build speed and accuracy by solving a graded set of questions on {T}",
           "apply": "apply {T} to unfamiliar, real-life and higher-order thinking (HOTS) problems",
           "revise": "recall and use the key ideas of {T} in a short assessment and correct their own mistakes"}
O1 = ["recognise and talk about {T} using objects, pictures and everyday examples",
      "identify and describe {T} with the help of familiar examples and simple representations",
      "explain the idea of {T} in their own words and illustrate it with suitable examples",
      "explain and justify the key ideas of {T} using correct terminology and representations",
      "analyse the key ideas of {T} and explain them with precise terminology, reasoning and representations"]
LO1 = ["Students recognise and talk about {T} using objects and pictures.",
       "Students identify and describe {T} with familiar examples.",
       "Students explain {T} in their own words and give suitable examples.",
       "Students explain and justify the key ideas of {T} using correct terminology.",
       "Students analyse and explain {T} with precise reasoning and representations."]
SK21 = {"full": ["Critical thinking", "Communication", "Collaboration", "Problem solving"],
        "intro": ["Curiosity and inquiry", "Communication", "Critical thinking", "Collaboration"],
        "build": ["Critical thinking", "Communication", "Visualisation", "Collaboration"],
        "practice": ["Problem solving", "Perseverance", "Self-discipline", "Peer learning"],
        "apply": ["Creativity", "Decision making", "Real-world problem solving", "Collaboration"],
        "revise": ["Self-assessment", "Metacognition", "Time management", "Communication"]}
M_KIND_SKILL = {"D": "Data literacy", "G": "Spatial reasoning", "T": "Digital literacy", "M": "Estimation and measurement",
                "N": "Numeracy", "R": "Financial literacy", "A": "Logical reasoning", "P": "Pattern recognition"}
M_KIND_COMP = {"D": "Data interpretation", "G": "Spatial visualisation", "A": "Symbolic representation",
               "M": "Application of measurement", "T": "Modelling", "R": "Everyday numeracy", "N": "Number sense", "P": "Pattern recognition"}
M_STRAT = {"full": "Concrete-Pictorial-Abstract (CPA) approach; Think-Pair-Share; guided practice with peer support",
           "intro": "Concrete-Pictorial-Abstract (CPA) approach; guided discovery; Think-Pair-Share",
           "build": "Worked examples with think-aloud; questioning technique; peer explanation",
           "practice": "Scaffolded practice; peer tutoring; differentiated tasks (support, core, challenge)",
           "apply": "Problem-based learning; collaborative group work; real-life context tasks",
           "revise": "Retrieval practice; error analysis; gamified quiz"}
M_AIDS = {"N": "number cards, counters, fraction strips or a place-value chart as needed", "A": "algebra tiles or balance diagram, worksheets",
          "G": "geometry box, paper strips and cut-outs, GeoGebra (if available)", "M": "measuring tape, grid or graph paper, unit cubes",
          "D": "chart paper, class data sheet, graph paper", "R": "price tags or play money, ratio tables, calculator",
          "T": "graph paper, scientific calculator, GeoGebra (if available)", "P": "pattern cards, beads or matchsticks, worksheets",
          "X": "charts and worksheets"}

def _warm(ph, T, chap, e, seed):
    if ph in ("full", "intro"):
        return sent("%s. Invite 3-4 students to share what they notice and what they already know about %s (5 min)" % (e["hook"].rstrip("."), Q(T)))
    if ph == "build":
        return pick(["Quick recall (5 min): ask 4-5 oral questions from the previous lesson on %s; students answer on slates or mini-whiteboards." % Q(T),
                     "Recap relay (5 min): students pass a ball and each states one fact they remember about %s." % Q(T)], seed, T)
    if ph == "practice":
        return pick(["Mental maths sprint (5 min): 5 rapid oral questions linked to %s; students show answers on slates and correct errors together." % Q(T),
                     "Match-up starter (5 min): students match 5 questions on %s with their answers on cards." % Q(T)], seed, T)
    if ph == "apply":
        return "Puzzle starter (5 min): present a short real-life puzzle connected to %s and let pairs predict the answer before the lesson begins." % Q(T)
    return "Memory chain (5 min): each student adds one key fact or rule about %s; the teacher notes gaps to revisit." % Q(chap or T)

M_STEPS = {
 "full": [(15, "Introduction", "Link {T} with {prior}; write the topic on the board and share the learning objectives."),
          (35, "Concept building", "{act}. Guide students to describe what they observe and to state the idea of {T} in their own words."),
          (25, "Worked examples", "Solve two examples from the NCERT textbook on the board using the think-aloud method; point out key terms and common errors."),
          (25, "Guided practice", "Pairs solve 3-4 questions of increasing difficulty; the teacher moves around, questions and gives instant feedback.")],
 "intro": [(15, "Introduction", "Link {T} with {prior}; share the learning objectives and key vocabulary."),
           (45, "Concept building", "{act}. Students record their findings in their notebooks."),
           (25, "Discussion", "Students state the idea of {T} in their own words; the teacher consolidates with a labelled chart and one worked example."),
           (15, "Check for understanding", "Students answer 2-3 quick questions on slates; the teacher notes who needs support.")],
 "build": [(15, "Revisit", "Recap the idea of {T} with the previous day's notes and key vocabulary."),
           (35, "Worked examples", "Solve three graded examples from the NCERT textbook on the board (easy, medium, challenging), thinking aloud at each step."),
           (30, "Try it yourself", "Students attempt a similar example in pairs and explain their steps to the class; the teacher corrects common misconceptions."),
           (20, "Notes", "Students make concise notes or a mind-map of {T} with definitions, rules and one solved example.")],
 "practice": [(10, "Targets", "Explain the day's practice targets and success criteria."),
              (45, "Independent practice", "Students work on a graded worksheet or NCERT exercise questions on {T}: Level 1 (basic), Level 2 (standard), Level 3 (challenge)."),
              (20, "Peer checking", "Partners exchange notebooks, check each other's work against a checklist and discuss mistakes."),
              (25, "Teacher support", "The teacher supports small groups who need help while others attempt extension problems.")],
 "apply": [(15, "Context", "Present a real-life situation involving {T} (such as {real1}); students identify what is given and what is to be found."),
           (45, "Group problem solving", "Groups of four solve a multi-step or HOTS problem on {T} and prepare a short explanation or chart."),
           (25, "Presentations", "Groups present their solutions; the class asks questions and compares methods."),
           (15, "Teacher summary", "Highlight the most efficient strategies and link the solutions to the key ideas of {T}.")],
 "revise": [(25, "Concept recap", "Recap all key ideas, rules and vocabulary of {T} and {chap} with a mind-map on the board."),
            (25, "Doubt clearing", "Students post doubts on slips; the teacher answers them with fresh examples."),
            (40, "Assessment", "Short written assessment (10 marks): MCQs, short answers and one application question on {T}."),
            (10, "Self-check", "Students check answers against the key, mark their own work and note areas to improve.")]}

def _wrap(ph, T, b, seed):
    if b == 0 and ph != "revise":
        return "Class rhyme or action game that revisits %s; each child draws or says one thing they learnt (5 min)." % Q(T)
    return {"full": "Exit ticket (5 min): each student writes or says one thing learnt about %s and one question; recap the learning objectives." % Q(T),
            "intro": "Exit ticket (5 min): each student writes one thing learnt about %s and one question; recap the learning objectives." % Q(T),
            "build": "Summary circle (5 min): each student adds one rule or fact to a class summary chart; the teacher confirms the key points.",
            "practice": "Error hunt (5 min): the teacher shows two worked solutions with deliberate mistakes; students find and correct them.",
            "apply": "Reflect and share (5 min): each group states one strategy that helped; the class votes on the best real-life use of %s." % Q(T),
            "revise": "Self-assessment (5 min): students show red, yellow or green cards to rate their confidence in each part of %s." % Q(T)}[ph]

def _assess(ph, b):
    base = {"full": "Formative: oral questioning and observation during the activity; 3-question quick check on slates; participation checklist.",
            "intro": "Formative: oral questioning and observation during the activity; 3-question quick check on slates; participation checklist.",
            "build": "Formative: accuracy of student examples, questioning and a review of notebook notes.",
            "practice": "Formative: worksheet marking with feedback using a 3-level rubric (needs support, meeting, exceeding).",
            "apply": "Rubric-based assessment of the group solution (accuracy, reasoning, communication, teamwork).",
            "revise": "Summative-style: 10-mark written test (MCQ, short answer and one competency-based question); marks recorded."}[ph]
    if b >= 3 and ph in ("practice", "revise", "apply"):
        base += " Include one case-based or assertion-reason question."
    if b == 0:
        base = "Oral questions and observation of hands-on work; simple picture or object-based tasks."
    return base

def _homework(ph, T, chap, b):
    if ph == "revise":
        return "Revise your notes of %s, attempt the practice sheet and correct all mistakes from today's assessment." % Q(chap or T)
    h = ["Draw or collect pictures and objects related to %s and talk about them with your family; try 2 simple practice sums." % Q(T),
         "Solve 4-5 simple questions on %s in your notebook and make a small drawing or chart showing one example." % Q(T),
         "Solve the selected NCERT exercise questions on %s (5-6 questions) and create one real-life problem of your own." % Q(T),
         "Solve the selected NCERT exercise questions and 2 additional problems on %s; write a short summary of the key rules or formulae." % Q(T),
         "Solve the selected NCERT exercise and 2 previous-year style questions on %s; prepare a concise concept and formula sheet." % Q(T)][b]
    if ph == "intro":
        h += " Note down 2 doubts to ask in the next class."
    return h

def build_math_day(grade, chapter, topic, phase, minutes, e, seed, day, teacher, date, shown=None):
    b = band(grade); T = topic; kind = e["kind"]; fm = {"T": Q(T), "chap": chapter or T}
    o2 = (M_PH_O2.get(phase) or ("solve simple problems on {T} with the help of objects and pictures" if b == 0 else M_SK.get(kind, M_SK["X"]))).format(**fm)
    o3 = "reflect on their own learning in %s and identify what needs more practice" % Q(chapter or T) if phase == "revise" else \
         ("talk about where we see %s in daily life" % Q(T) if b == 0 else
          "connect %s to real life (for example, %s) and communicate their reasoning clearly" % (Q(T), e["real"]))
    obj = "Students will be able to:\n1. %s.\n2. %s.\n3. %s." % (cap(O1[b].format(**fm)), cap(o2), cap(o3))
    sk = list(SK21[phase]); sk[3] = M_KIND_SKILL.get(kind, sk[3]) if phase in ("full", "intro", "build") else sk[3]
    comp = ["Conceptual understanding", M_KIND_COMP.get(kind, "Logical reasoning"), "Mathematical reasoning", "Application to real-life situations"]
    strat = M_STRAT[phase]
    if b <= 1:
        strat = "Play-way and activity-based learning; " + strat.split("; ", 1)[-1]
    res = "NCERT Mathematics textbook (Class %s); blackboard or whiteboard; %s" % (grade, M_AIDS.get(kind, M_AIDS["X"]))
    if phase == "revise":
        res += "; quiz slips and assessment sheet"
    elif phase == "practice":
        res += "; graded worksheet"
    body = max(minutes - 10, 4)
    steps = M_STEPS[phase]
    mins = split_minutes(body, [s[0] for s in steps])
    real1 = e["real"].split(",")[0]
    proc = ["%s (%d min): %s" % (lab, m, txt.format(T=Q(T), prior=e["prior"], act=e["act"].rstrip("."), real1=real1, chap=Q(chapter or T)))
            for (w, lab, txt), m in zip(steps, mins)]
    lo2 = {"practice": "Students solve graded questions on {T} with improved speed and accuracy.",
           "apply": "Students apply {T} to real-life and higher-order problems and justify their method.",
           "revise": "Students recall the key ideas of {T} and correct their own mistakes."}.get(phase,
            "Students solve problems on {T} correctly using appropriate steps." if b else "Students solve simple problems on {T} using objects and pictures.")
    outcomes = [LO1[b].format(T=Q(T)), lo2.format(T=Q(T)), "Students relate %s to real life and explain their reasoning." % Q(T)]
    return {"subject": "Mathematics", "grade": str(grade), "teacher": teacher, "chapter": chapter,
            "topic": topic_line(shown or T, phase), "time": "%d minutes" % minutes, "dfrom": dmy(date), "dto": dmy(date),
            "objective": obj, "skills": ", ".join(sk), "competencies": ", ".join(comp), "strategies": strat,
            "resources": res, "warmup": _warm(phase, T, chapter, e, seed), "procedure": proc,
            "interdisc": e["inter"], "sdg": sdg_text(e["sdg"]), "wrap": _wrap(phase, T, b, seed),
            "assessment": _assess(phase, b), "outcomes": outcomes, "homework": _homework(phase, T, chapter, b)}

# ------------------------------------------------------------------ SCIENCE builders
REFLECT = ["What went well during the class?", "Were there any challenges or areas where students struggled?",
           "How did students respond to the activities and instruction?", "Were the learning objectives met? If not, why?",
           "What adjustments could be made to improve future lessons?",
           "What insights were gained about student learning preferences or needs?"]
MROWS = [("CHAPTER", "t"), ("TEXTBOOK", "t"), ("CLASS TRANSACTION", "t"), ("TEACHING AIDS / RESOURCES / LINKS / WEBSITES", "t"),
         ("LEARNING OBJECTIVES", "l"), ("SDG", "t"), ("INTER-DISCIPLINARY INTEGRATION", "t"),
         ("21ST CENTURY SKILLS AND COMPETENCIES INCORPORATED", "t"), ("TEACHING STRATEGIES USED", "t"),
         ("TRANSACTION METHODOLOGY", "t"), ("LEARNING OUTCOMES", "l"), ("ASSESSMENT AND ACTIVITIES", "t"),
         ("CLASS / HOME ASSIGNMENT", "t"), ("PLENARY ACTIVITIES / WRAP-UP", "t")]
DROWS = [("DATE", "t"), ("TIME DURATION OF CLASS", "t"), ("TOPIC / SUB-TOPIC", "t"), ("TEACHING AIDS / RESOURCES", "t"),
         ("LEARNING OBJECTIVES", "l"), ("SDG", "t"), ("21ST CENTURY SKILLS / VALUES INCORPORATED", "t"),
         ("PRE-REQUISITE KNOWLEDGE REQUIRED", "t"), ("TEACHING METHODOLOGY", "l"), ("TEACHING STRATEGY", "t"),
         ("LEARNING OUTCOMES", "l"), ("CLASS / HOME ASSIGNMENT", "t"), ("SKILL / VALUES IMBIBED", "t"),
         ("PLENARY ACTIVITIES / WRAP-UP", "t"), ("REFLECTION", "r")]

S_SK = {"B": "observe, draw and label the structures or processes involved in {T}",
        "C": "observe changes safely, record observations and draw conclusions about {T}",
        "P": "perform simple measurements or observations and interpret the results related to {T}",
        "E": "interpret charts, maps or data about {T} and relate them to their surroundings",
        "X": "observe, record and discuss findings related to {T}"}
S_RES = {"B": "NCERT Science textbook, charts and models, microscope or hand lens, specimens or pictures, whiteboard",
         "C": "NCERT Science textbook, simple lab materials (safe household substances), charts and models, whiteboard",
         "P": "NCERT Science textbook, simple apparatus (spring balance, torch, cell and bulb, etc.), charts, PhET simulation (if available)",
         "E": "NCERT Science textbook, maps, charts or globe, models, pictures or short video clips (if available)",
         "X": "NCERT Science textbook, charts and models, simple apparatus, whiteboard"}
S_STRAT = {"full": "5E learning cycle; inquiry-based learning; Think-Pair-Share; teacher demonstration",
           "intro": "5E learning cycle; inquiry-based learning; Think-Pair-Share; teacher demonstration",
           "build": "5E learning cycle; concept mapping; collaborative group work; questioning technique",
           "practice": "5E learning cycle; scaffolded practice; peer learning; differentiated tasks",
           "apply": "5E learning cycle; project-based learning; collaborative group work; presentations",
           "revise": "5E learning cycle; retrieval practice; concept mapping; gamified quiz"}
S_STEPS = {
 "full": [(15, "Engage", "{hook}."), (30, "Explore", "{act}."),
          (25, "Explain", "Consolidate the concept of {T} with labelled diagrams or charts; define the key terms and let students note them."),
          (20, "Elaborate", "Link {T} to real life (such as {real1}) and discuss application questions."),
          (10, "Evaluate", "Exit-ticket quiz of 3 questions (MCQ and short answer).")],
 "intro": [(15, "Engage", "{hook}."), (40, "Explore", "{act}."),
           (25, "Explain", "Consolidate the concept of {T} with labelled diagrams or charts; define the key terms and let students note them."),
           (5, "Elaborate", "Pose one 'what if' question for students to think about."),
           (15, "Evaluate", "Quick check with 3 oral or slate questions.")],
 "build": [(15, "Engage", "Recap the previous lesson with 3 oral questions on {T}."),
           (30, "Explore", "In groups, students study diagrams, models or data on {T} and answer guiding questions."),
           (30, "Explain", "Clarify the concepts and processes with labelled diagrams and correct misconceptions."),
           (15, "Elaborate", "Connect {T} to real life (such as {real1})."),
           (10, "Evaluate", "Label-the-diagram or true/false quick quiz.")],
 "practice": [(10, "Engage", "Quick recall quiz on {T}."),
              (40, "Explore", "Groups solve NCERT questions or a worksheet (diagrams, reasoning, numericals where relevant) on {T}."),
              (20, "Explain", "Discuss the answers and common errors."),
              (15, "Elaborate", "Extension with HOTS and competency-based questions."),
              (15, "Evaluate", "Peer checking against an answer key.")],
 "apply": [(10, "Engage", "Present a real-life problem related to {T} (such as {real1})."),
           (40, "Explore", "Groups design a small model, poster or investigation on {T}."),
           (25, "Explain", "Groups present their findings and the class asks questions."),
           (15, "Elaborate", "Link the work to the SDGs and everyday decisions."),
           (10, "Evaluate", "Score the presentations with a rubric.")],
 "revise": [(15, "Engage", "Build a concept map of {T} on the board with student help."),
            (30, "Explore", "Revision stations or a quiz game covering key terms, diagrams and reasoning."),
            (15, "Explain", "Clear doubts using fresh examples."),
            (10, "Elaborate", "Discuss one case-based question."),
            (30, "Evaluate", "Short written test (10 marks).")]}
S_CLASS = {"full": "Draw and label a neat diagram or complete the activity sheet on {T}.",
           "intro": "Draw and label a neat diagram or complete the activity sheet on {T}.",
           "build": "Answer 3-4 NCERT in-text questions on {T} in the notebook.",
           "practice": "Complete the worksheet on {T}.",
           "apply": "Finish the model, poster or investigation report on {T}.",
           "revise": "Attempt the test and correct all mistakes."}
S_HOME = ["Look for something related to {T} at home and draw it.",
          "Write 4-5 sentences about {T} and draw a labelled diagram.",
          "Answer the selected NCERT questions on {T} and write one real-life example.",
          "Answer the selected NCERT questions on {T} and prepare short notes or a flow chart.",
          "Solve the selected NCERT questions on {T} and prepare a concise concept map with previous-year style questions."]
S_VALUES = {"B": "Observation and recording; care for living things; teamwork", "C": "Safe handling of materials; accurate observation; patience",
            "P": "Measurement and data handling; logical reasoning; teamwork", "E": "Responsibility towards the environment; observation; global citizenship",
            "X": "Scientific temper; curiosity; teamwork"}

def _joinlist(items, limit=3):
    items = items[:limit]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]

def _sci_objectives(b, T, kind, phase, e, chapter=None):
    fm = {"T": T}
    o2 = (M_PH_O2.get(phase) or S_SK.get(kind, S_SK["X"])).format(T=Q(T))
    if phase == "revise":
        o3 = "reflect on their own learning in %s and identify what needs more practice" % Q(chapter or T)
    else:
        o3 = "connect %s to everyday life (for example, %s)" % (Q(T), e["real"])
    o4 = "develop curiosity and care for living things and the surroundings" if b <= 1 else "develop scientific temper, curiosity and concern for health and the environment"
    return [sent(O1[b].format(T=Q(T))), sent(o2), sent(o3), sent(o4)]

def _sci_outcomes(b, T, kind, phase):
    k = {"B": "Students draw, label and explain the structures or processes in {T}.",
         "C": "Students record observations safely and draw conclusions about {T}.",
         "P": "Students measure or observe and interpret results related to {T}.",
         "E": "Students interpret charts or data on {T} and relate them to their surroundings.",
         "X": "Students observe, record and explain findings related to {T}."}[kind if kind in S_SK else "X"]
    k = {"practice": "Students answer graded questions on {T} with accuracy.",
         "apply": "Students apply {T} to a real-life problem and present their findings.",
         "revise": "Students recall the key ideas of {T} and correct their own mistakes."}.get(phase, k)
    return [LO1[b].format(T=Q(T)), k.format(T=Q(T)), "Students relate %s to everyday life and explain their reasoning." % Q(T)]

def build_sci_day(grade, chapter, topic, phase, minutes, e, seed, date, shown=None):
    b = band(grade); T = topic; kind = e["kind"] if e["kind"] in S_SK else "X"
    sk = list(SK21[phase]); sk[3] = "Scientific temper" if phase in ("full", "intro", "build") else sk[3]
    skills = ", ".join(sk) + "; values: curiosity, honesty in recording observations, care for the environment"
    steps = S_STEPS[phase]
    mins = split_minutes(minutes, [s[0] for s in steps])
    real1 = e["real"].split(",")[0]
    meth = ["%s (%d min): %s" % (lab, m, sent(txt.format(T=Q(T), hook=e["hook"].rstrip("."), act=e["act"].rstrip("."), real1=real1)))
            for (w, lab, txt), m in zip(steps, mins)]
    wrap = {"full": "Summary circle: each student states one thing learnt about %s; recap the learning objectives and answer the question box." % Q(T),
            "intro": "Summary circle: each student states one thing learnt about %s; recap the learning objectives and answer the question box." % Q(T),
            "build": "Students complete a one-minute summary of %s on a sticky note; the teacher confirms the key points." % Q(T),
            "practice": "Error hunt: the teacher shows two answers with deliberate mistakes; students find and correct them.",
            "apply": "Groups state one thing they would change in their work; the class gives two stars and a wish for each group.",
            "revise": "Self-assessment with red, yellow and green cards for each part of %s; note topics for remedial practice." % Q(T)}[phase]
    if b == 0:
        wrap = "Class rhyme or action game that revisits %s; each child draws or says one thing they learnt." % Q(T)
    return [dmy(date), "%d minutes" % minutes, topic_line(shown or T, phase), S_RES.get(kind, S_RES["X"]),
            _sci_objectives(b, T, kind, phase, e, chapter), sdg_text(e["sdg"]), skills,
            sent("Students should be familiar with %s" % e["prior"]), meth, S_STRAT[phase],
            _sci_outcomes(b, T, kind, phase),
            "Class: %s\nHome: %s" % (S_CLASS[phase].format(T=Q(T)), S_HOME[b].format(T=Q(T))),
            S_VALUES.get(kind, S_VALUES["X"]), wrap, list(REFLECT)]

def build_sci_month(grade, chapter, topics, dates, minutes, e, teacher):
    b = band(grade); kind = e["kind"] if e["kind"] in S_SK else "X"
    T = _joinlist(topics) if topics else chapter
    n = len(dates)
    span = dmy(dates[0]) if n == 1 else "%s to %s" % (dmy(dates[0]), dmy(dates[-1]))
    objs = [sent("Understand the key ideas of %s, including %s" % (Q(chapter), T)),
            sent(S_SK.get(kind, S_SK["X"]).format(T=Q(chapter))),
            sent("connect the chapter to everyday life (for example, %s)" % e["real"]),
            sent("develop curiosity and care for living things and the surroundings" if b <= 1 else "develop scientific temper, curiosity and concern for health and the environment")]
    outs = ["Students explain the main ideas of %s using correct terminology." % Q(chapter),
            S_SK.get(kind, S_SK["X"]).format(T=Q(chapter)),
            "Students relate the chapter to everyday life and explain their reasoning."]
    outs[1] = "Students " + outs[1].replace("observe", "observe", 1) + "."
    return [chapter, "NCERT Science textbook, Class %s" % grade,
            "%d class%s of %d minutes each (%s)" % (n, "" if n == 1 else "es", minutes, span),
            S_RES.get(kind, S_RES["X"]) + "; NCERT e-textbook (ncert.nic.in), DIKSHA and PhET simulations (phet.colorado.edu) when internet is available",
            objs, sdg_text(e["sdg"]), e["inter"],
            "Skills: critical thinking, communication, collaboration, problem solving. Competencies: scientific inquiry, conceptual understanding, application of concepts, scientific communication.",
            S_STRAT["full"],
            "5E learning cycle (Engage, Explore, Explain, Elaborate, Evaluate) with demonstrations, group activities, discussion and formative checks; lessons move from introduction to practice, application and revision across %d day%s." % (n, "" if n == 1 else "s"),
            outs,
            "Oral questioning, quizzes, observation of activities, worksheets, notebook checks and a short chapter test. Key activity: %s." % e["act"].rstrip("."),
            "Class: diagrams, worksheets and NCERT in-text questions.\nHome: selected NCERT exercise questions, short notes and one observation task.",
            "Exit tickets, summary circles and a concept map at the end of the chapter; self-assessment with red, yellow and green cards."]

# ------------------------------------------------------------------ main entry
def _tt(chapter, t, ph):
    """Text used inside sentences: a multi-topic revision day refers to the whole chapter."""
    return chapter if (ph == "revise" and ";" in t) else t

def autofill(p):
    subj = "sci" if p.get("subject") == "sci" else "math"
    grade = str(int(p.get("grade") or 6))
    chapter = clean(p.get("chapter"))
    topics = split_topics(p.get("topics"))
    if not chapter or not topics:
        raise ValueError("Please enter both the chapter and the topic.")
    minutes = max(10, min(120, int(p.get("minutes") or 40)))
    teacher = clean(p.get("teacher"))
    seed = int(p.get("seed") or 0)
    mode = "period" if p.get("mode") == "period" else "single"
    hol = set(p.get("holidays") or [])
    if mode == "single":
        dates = [parse_iso(p.get("date") or datetime.date.today().isoformat())]
        plan = [("; ".join(topics), p.get("phase") if p.get("phase") in PHASE_LABEL else "full")]
    else:
        if subj == "math" and p.get("range_type") == "month":
            y, m = int(p["month"][:4]), int(p["month"][5:7])
            a, z = datetime.date(y, m, 1), datetime.date(y, m, calendar.monthrange(y, m)[1])
        else:
            a, z = parse_iso(p["dfrom"]), parse_iso(p["dto"])
        dates = [d for d in date_range(a, z) if d.isoformat() not in hol]
        if not dates:
            raise ValueError("No teaching dates left in that period (check the dates and holidays).")
        if len(dates) > 62:
            raise ValueError("Please choose a period of 62 days or less.")
        plan = plan_days(topics, len(dates))
    e = analyze(subj, chapter, "; ".join(topics))
    now = datetime.datetime.now().isoformat(timespec="seconds")
    sess = clean(p.get("session")) or session_for(dates[0])
    st = {"id": uuid.uuid4().hex[:10], "kind": subj, "created": now, "updated": now,
          "params": {k: p.get(k) for k in ("subject", "mode", "grade", "chapter", "topics", "teacher", "minutes", "date",
                                              "month", "range_type", "dfrom", "dto", "holidays", "session")},
          "meta": {"grade": grade, "chapter": chapter, "topics": topics, "teacher": teacher, "session": sess,
                   "minutes": minutes, "seed": seed, "count": len(dates), "first": dmy(dates[0]), "last": dmy(dates[-1])}}
    st["params"]["seed"] = seed
    if subj == "math":
        st["docs"] = [{"day": i + 1, "f": build_math_day(grade, chapter, _tt(chapter, t, ph), ph, minutes, analyze("math", chapter, t),
                                                        seed + i, i + 1, teacher, d, shown=t)}
                      for i, (d, (t, ph)) in enumerate(zip(dates, plan))]
        st["title"] = "Mathematics \u00b7 Class %s \u00b7 %s" % (grade, chapter)
    else:
        mlabel = month_label(dates[0])
        if mode == "period" and p.get("month"):
            y, m = int(p["month"][:4]), int(p["month"][5:7])
            mlabel = "%s %d" % (calendar.month_name[m], y)
        st["month"] = {"name": mlabel, "sub": "Science", "gr": grade, "tc": teacher,
                       "dt": dmy(dates[0]) if len(dates) == 1 else "%s \u2013 %s" % (dmy(dates[0]), dmy(dates[-1])),
                       "topics": topics, "r": build_sci_month(grade, chapter, topics, dates, minutes, e, teacher)}
        st["days"] = [{"r": build_sci_day(grade, chapter, _tt(chapter, t, ph), ph, minutes, analyze("sci", chapter, t), seed + i, d, shown=t)}
                      for i, (d, (t, ph)) in enumerate(zip(dates, plan))]
        st["title"] = "Science \u00b7 Class %s \u00b7 %s" % (grade, chapter)
    st["title"] += " \u00b7 " + (dmy(dates[0]) if len(dates) == 1 else "%s \u2013 %s" % (dmy(dates[0]), dmy(dates[-1])))
    return st


# =====================================================================
#  PDF ENGINE (pure Python, no libraries, works fully offline)
#  Draws gradients, rounded cards, chips, tables, page numbers.
# =====================================================================
PW, PH = 595.28, 841.89
UMAP = {"\u2192": "->", "\u2190": "<-", "\u2264": "<=", "\u2265": ">=", "\u2260": "!=", "\u03c0": "pi", "\u03b8": "theta",
        "\u221a": "sqrt", "\u221e": "inf", "\u0394": "Delta", "\u03b1": "alpha", "\u03b2": "beta", "\u03b3": "gamma",
        "\u2220": "angle ", "\u25b3": "triangle ", "\u2212": "-", "\u00a0": " ", "\u2009": " ", "\u200b": "", "\u2713": "ok",
        "\u2714": "ok", "\u2248": "~", "\u00b7": "\u00b7", "\u2032": "'", "\u2033": '"', "\u2043": "-", "\u2010": "-", "\u2011": "-",
        "\t": " ", "\r": ""}

def enc(s):
    s = "".join(UMAP.get(c, c) for c in str(s))
    return s.encode("cp1252", "replace")

def tw(s, bold=False, size=10):
    t = WID_B if bold else WID_R
    return sum(t[b - 32] if 32 <= b <= 255 else 0 for b in enc(s)) * size / 1000.0

def _pdfstr(b):
    out = bytearray(b"(")
    for c in b:
        if c in (40, 41, 92):
            out += b"\\" + bytes([c])
        elif 32 <= c < 127:
            out.append(c)
        else:
            out += ("\\%03o" % c).encode()
    out += b")"
    return bytes(out)

def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

def _c(h):
    return "%.3f %.3f %.3f" % rgb(h)

class Page:
    def __init__(self, pdf):
        self.pdf, self.o, self.post = pdf, [], None

    def add(self, s):
        self.o.append(s)

    def _path(self, x, y, w, h, r):
        if not isinstance(r, (tuple, list)):
            r = (r, r, r, r)
        tl, tr, br, bl = r
        X0, X1, Y0, Y1 = x, x + w, PH - y - h, PH - y
        k = 0.5523
        p = ["%.2f %.2f m" % (X0 + bl, Y0), "%.2f %.2f l" % (X1 - br, Y0)]
        if br:
            p.append("%.2f %.2f %.2f %.2f %.2f %.2f c" % (X1 - br + br * k, Y0, X1, Y0 + br - br * k, X1, Y0 + br))
        p.append("%.2f %.2f l" % (X1, Y1 - tr))
        if tr:
            p.append("%.2f %.2f %.2f %.2f %.2f %.2f c" % (X1, Y1 - tr + tr * k, X1 - tr + tr * k, Y1, X1 - tr, Y1))
        p.append("%.2f %.2f l" % (X0 + tl, Y1))
        if tl:
            p.append("%.2f %.2f %.2f %.2f %.2f %.2f c" % (X0 + tl - tl * k, Y1, X0, Y1 - tl + tl * k, X0, Y1 - tl))
        p.append("%.2f %.2f l" % (X0, Y0 + bl))
        if bl:
            p.append("%.2f %.2f %.2f %.2f %.2f %.2f c" % (X0, Y0 + bl - bl * k, X0 + bl - bl * k, Y0, X0 + bl, Y0))
        p.append("h")
        return " ".join(p)

    def rect(self, x, y, w, h, fill=None, stroke=None, lw=0.6, r=0):
        op = ("B" if fill and stroke else "f" if fill else "S")
        s = ""
        if fill:
            s += _c(fill) + " rg "
        if stroke:
            s += _c(stroke) + " RG %.2f w " % lw
        self.add(s + self._path(x, y, w, h, r) + " " + op)

    def line(self, x1, y1, x2, y2, color="#d5dcea", lw=0.6, dash=None):
        d = "[%s] 0 d " % dash if dash else ""
        self.add("%s%s RG %.2f w %.2f %.2f m %.2f %.2f l S%s" % (d, _c(color), lw, x1, PH - y1, x2, PH - y2, " [] 0 d" if dash else ""))

    def circle(self, cx, cy, r, fill):
        k = 0.5523 * r
        X, Y = cx, PH - cy
        self.add("%s rg %.2f %.2f m %.2f %.2f %.2f %.2f %.2f %.2f c %.2f %.2f %.2f %.2f %.2f %.2f c %.2f %.2f %.2f %.2f %.2f %.2f c %.2f %.2f %.2f %.2f %.2f %.2f c f" % (
            _c(fill), X + r, Y, X + r, Y + k, X + k, Y + r, X, Y + r, X - k, Y + r, X - r, Y + k, X - r, Y,
            X - r, Y - k, X - k, Y - r, X, Y - r, X + k, Y - r, X + r, Y - k, X + r, Y))

    def push(self):
        self.add("q")

    def pop(self):
        self.add("Q")

    def alpha(self, a):
        self.add("q /%s gs" % self.pdf.alpha_name(a))

    def clip(self, x, y, w, h, r=0):
        self.add(self._path(x, y, w, h, r) + " W n")

    def gradient(self, x, y, w, h, c1, c2, r=0, diag=True):
        nm = self.pdf.shade_name(c1, c2, x, PH - y, x + w, PH - y - h) if diag else self.pdf.shade_name(c1, c2, x, 0, x + w, 0)
        self.add("q " + self._path(x, y, w, h, r) + " W n /%s sh Q" % nm)

    def text(self, x, y, s, size=9, bold=False, color="#1f2a44", tc=0, italic=False):
        if not s:
            return
        f = "F2" if bold else ("F3" if italic else "F1")
        self.o.append(b"BT /%s %.2f Tf %s rg %.2f Tc %.2f %.2f Td " % (f.encode(), size, _c(color).encode(), tc, x, PH - y) + _pdfstr(enc(s)) + b" Tj ET")

    def ctext(self, cx, y, s, size=9, bold=False, color="#1f2a44", tc=0):
        self.text(cx - (tw(s, bold, size) + tc * len(s)) / 2.0, y, s, size, bold, color, tc)

    def rtext(self, xr, y, s, size=9, bold=False, color="#1f2a44"):
        self.text(xr - tw(s, bold, size), y, s, size, bold, color)

    def rot_text(self, cx, cy, s, size, ang, color, bold=True):
        a = math.radians(ang)
        c, sn = math.cos(a), math.sin(a)
        w = tw(s, bold, size)
        x0, y0 = cx - (w / 2) * c, (PH - cy) - (w / 2) * sn
        self.o.append(b"BT /%s %.2f Tf %s rg %.3f %.3f %.3f %.3f %.2f %.2f Tm " % (
            b"F2" if bold else b"F1", size, _c(color).encode(), c, sn, -sn, c, x0, y0) + _pdfstr(enc(s)) + b" Tj ET")


class Pdf:
    def __init__(self, title="", author=""):
        self.pages, self.title, self.author = [], title, author
        self.shades, self.alphas = [], []

    def add_page(self):
        p = Page(self)
        self.pages.append(p)
        return p

    def shade_name(self, c1, c2, x0, y0, x1, y1):
        key = (c1, c2, round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1))
        if key not in self.shades:
            self.shades.append(key)
        return "Sh%d" % self.shades.index(key)

    def alpha_name(self, a):
        if a not in self.alphas:
            self.alphas.append(a)
        return "GS%d" % self.alphas.index(a)

    def build(self):
        n = len(self.pages)
        for i, p in enumerate(self.pages):
            if p.post:
                p.post(p, i + 1, n)
        objs = []
        def add(b):
            objs.append(b if isinstance(b, bytes) else b.encode("latin-1"))
            return len(objs)
        add("")  # 1 catalog (filled later)
        add("")  # 2 pages
        fonts = [add("<< /Type /Font /Subtype /Type1 /BaseFont /%s /Encoding /WinAnsiEncoding >>" % f)
                 for f in ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique")]
        def fn(c0, c1):
            return "<< /FunctionType 2 /Domain [0 1] /C0 [%.3f %.3f %.3f] /C1 [%.3f %.3f %.3f] /N 1 >>" % (rgb(c0) + rgb(c1))
        sh = " ".join("/Sh%d << /ShadingType 2 /ColorSpace /DeviceRGB /Coords [%.2f %.2f %.2f %.2f] /Function %s /Extend [true true] >>" % (
            i, k[2], k[3], k[4], k[5], fn(k[0], k[1])) for i, k in enumerate(self.shades))
        gs = " ".join("/GS%d << /ca %.3f /CA %.3f >>" % (i, a, a) for i, a in enumerate(self.alphas))
        res = add("<< /Font << /F1 %d 0 R /F2 %d 0 R /F3 %d 0 R >> /Shading << %s >> /ExtGState << %s >> >>" % (fonts[0], fonts[1], fonts[2], sh, gs))
        kids = []
        for p in self.pages:
            data = b"\n".join(x if isinstance(x, bytes) else x.encode("latin-1") for x in p.o)
            z = zlib.compress(data, 6)
            c = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(z) + z + b"\nendstream")
            kids.append(add("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.2f %.2f] /Resources %d 0 R /Contents %d 0 R >>" % (PW, PH, res, c)))
        title = "<FEFF" + self.title.encode("utf-16-be").hex().upper() + ">"
        author = "<FEFF" + self.author.encode("utf-16-be").hex().upper() + ">"
        now = datetime.datetime.now().strftime("D:%Y%m%d%H%M%S")
        info = add("<< /Title %s /Author %s /Creator (NPS Lesson Planner) /Producer (NPS Lesson Planner) /CreationDate (%s) >>" % (title, author, now))
        objs[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
        objs[1] = ("<< /Type /Pages /Count %d /Kids [%s] >>" % (n, " ".join("%d 0 R" % k for k in kids))).encode()
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offs = []
        for i, b in enumerate(objs):
            offs.append(len(out))
            out += b"%d 0 obj\n" % (i + 1) + b + b"\nendobj\n"
        x = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
        for o in offs:
            out += b"%010d 00000 n \n" % o
        out += b"trailer\n<< /Size %d /Root 1 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, info, x)
        return bytes(out)

# ------------------------------------------------------------------ text layout
LBLRX = re.compile(r"^([A-Z][^:\n]{1,46}):\s+(?=\S)")

def _tokens(line):
    out = []
    m = LBLRX.match(line)
    if m and len(m.group(1).split()) <= 7:
        out += [(w, True) for w in (m.group(1) + ":").split(" ") if w]
        rest = line[m.end():]
    elif line.endswith(":") and len(line.split()) <= 7 and line[:1].isupper():
        return [(w, True) for w in line.split(" ") if w]
    else:
        rest = line
    return out + [(w, False) for w in rest.split(" ") if w]

def _wraptok(tokens, width, size):
    lines, cur, cw = [], [], 0.0
    sp = tw(" ", False, size)
    for w, b in tokens:
        ww = tw(w, b, size)
        while ww > width and len(w) > 1:       # very long word: split
            k = max(1, int(len(w) * width / ww) - 1)
            if cur:
                lines.append(cur); cur, cw = [], 0.0
            lines.append([(w[:k], b)])
            w = w[k:]; ww = tw(w, b, size)
        if cur and cw + sp + ww > width:
            lines.append(cur); cur, cw = [], 0.0
        cw += (sp if cur else 0) + ww
        cur.append((w, b))
    if cur or not lines:
        lines.append(cur)
    return lines

def _segs(words):
    segs = []
    for w, b in words:
        if segs and segs[-1][1] == b:
            segs[-1][0] += " " + w
        else:
            if segs:
                segs[-1][0] += " "
            segs.append([w, b])
    return segs

def text_lines(text, width, size):
    """-> list of (mark, indent, segs). Handles \\n paragraphs and '1.' numbering."""
    out = []
    for par in str(text or "").split("\n"):
        par = par.strip()
        if not par:
            continue
        m = re.match(r"^(\d+\.)\s+", par)
        ind = tw(m.group(1) + "  ", False, size) if m else 0
        rest = par[m.end():] if m else par
        ls = _wraptok(_tokens(rest), width - ind, size)
        for i, words in enumerate(ls):
            out.append((m.group(1) if (m and i == 0) else None, ind, _segs(words)))
    return out

def list_lines(items, width, size):
    out = []
    ind = 11
    for it in items or []:
        it = clean(it) if "\n" not in str(it) else str(it).strip()
        if not it:
            continue
        ls = _wraptok(_tokens(it), width - ind, size)
        for i, words in enumerate(ls):
            out.append(("\u2022" if i == 0 else None, ind, _segs(words)))
    return out

def draw_lines(pg, lines, x, y, size, lh, color="#1f2a44", markcolor=None):
    for mark, ind, segs in lines:
        base = y + (lh - size) / 2.0 + size * 0.80
        if mark:
            pg.text(x, base, mark, size, bool(mark != "\u2022"), markcolor or color)
        cx = x + ind
        for s, b in segs:
            pg.text(cx, base, s, size, b, color)
            cx += tw(s, b, size)
        y += lh
    return y

def as_list(v):
    if isinstance(v, list):
        return v
    return [x for x in str(v or "").split("\n") if x.strip()]

# ------------------------------------------------------------------ shared drawing bits
INK, MUTED, BRAND, BRAND_D, ACC, ACC_S, LINE, TINT, BG = ("#1f2a44", "#5d6b86", "#1d4e89", "#12335c", "#2eb67d",
                                                           "#e6f7ef", "#d5dcea", "#f3f6fb", "#eef2f8")

def deco_circles(pg, x, y, w, h, r, spots, color="#ffffff", a=0.07):
    pg.push(); pg.clip(x, y, w, h, r); pg.alpha(a)
    for cx, cy, rad in spots:
        pg.circle(cx, cy, rad, color)
    pg.pop(); pg.pop()

def label_width(label, size=6.8, tc=0.5):
    w = 0
    for i, part in enumerate(re.split(r"\{(.*?)\}", label)):
        w += tw(part, True, size * (0.68 if i % 2 else 1)) + tc * len(part)
    return w

def draw_label(pg, x, y, label, size=6.8, tc=0.5, color=BRAND_D):
    cx = x
    for i, part in enumerate(re.split(r"\{(.*?)\}", label)):
        sup = i % 2 == 1
        sz = size * (0.68 if sup else 1)
        pg.text(cx, y - (2.4 if sup else 0), part, sz, True, color, tc)
        cx += tw(part, True, sz) + tc * len(part)

# ------------------------------------------------------------------ MATHEMATICS card renderer
MATH_LAYOUT = [
    ("c3", [("SUBJECT:", "subject", 0, 0), ("GRADE:", "grade", 0, 0), ("TEACHER:", "teacher", 0, 0)]),
    ("c1", [("NAME OF THE CHAPTER:", "chapter", 0, 0)]),
    ("c1", [("TOPIC/SUB-TOPIC:", "topic", 0, 0)]),
    ("c3", [("TIME:", "time", 0, 0), ("DATE FROM:", "dfrom", 0, 0), ("DATE TO:", "dto", 0, 0)]),
    ("c1", [("LEARNING OBJECTIVE:", "objective", 0, 0)]),
    ("c2", [("21{ST} CENTURY SKILLS:", "skills", 1, 0), ("COMPETENCIES INCORPORATED:", "competencies", 1, 0)]),
    ("c2", [("STRATEGIES USED:", "strategies", 0, 0), ("RESOURCES USED", "resources", 0, 0)]),
    ("c1", [("WARM UP ACTIVITY:", "warmup", 1, 0)]),
    ("c1", [("PROCEDURE:", "procedure", 0, 1)]),
    ("c2", [("INTERDISCIPLINARY INTEGRATION:", "interdisc", 1, 0), ("SDG:", "sdg", 1, 0)]),
    ("c1", [(LBL_WRAP, "wrap", 0, 0)]),
    ("c1", [("ASSESSMENT:", "assessment", 0, 0)]),
    ("c1", [("LEARNING OUTCOMES:", "outcomes", 0, 1)]),
    ("c1", [("HOME ASSIGNMENT:", "homework", 1, 0)]),
]

class MathR:
    M, PAD, S, LH = 22, 14, 8.8, 12.2

    def __init__(self, pdf, session):
        self.pdf, self.session = pdf, session
        self.cw = PW - 2 * self.M
        self.top, self.bot = self.M, PH - 36
        self.x0, self.bw = self.M + self.PAD, self.cw - 2 * self.PAD
        self.limit = self.bot - 34

    def new_page(self, first):
        pg = self.pdf.add_page()
        self.pg = pg
        M, cw = self.M, self.cw
        pg.rect(0, 0, PW, PH, fill=BG)
        pg.alpha(0.10); pg.rect(M + 1, self.top + 4, cw, self.bot - self.top, fill=BRAND_D, r=12); pg.pop()
        pg.rect(M, self.top, cw, self.bot - self.top, fill="#ffffff", stroke=LINE, lw=0.8, r=12)
        pg.alpha(0.035); pg.rot_text(PW / 2, PH / 2 + 20, "NPS INTERNATIONAL SCHOOL", 30, 52, BRAND); pg.pop()
        day = "Day \u2013 %s" % self.day
        if first:
            h = 98
            pg.gradient(M, self.top, cw, h, BRAND_D, BRAND, r=(12, 12, 0, 0))
            deco_circles(pg, M, self.top, cw, h, (12, 12, 0, 0), [(M + cw - 40, self.top + 14, 74), (M + cw - 112, self.top + 102, 46), (M + 34, self.top + 108, 52), (M + 120, self.top - 8, 30)])
            pg.ctext(PW / 2, self.top + 27, SCHOOL_MATH, 9.5, True, "#ffffff", tc=2.2)
            pg.ctext(PW / 2, self.top + 55, "LESSON PLAN %s" % self.session, 23, True, "#ffffff", tc=1.0)
            pw_ = tw(day, True, 11) + 36
            pg.rect(PW / 2 - pw_ / 2, self.top + 65, pw_, 22, fill=ACC, r=11)
            pg.ctext(PW / 2, self.top + 80, day, 11, True, "#ffffff")
            pg.rect(M, self.top + h, cw, 3, fill=ACC)
            self.y = self.top + h + 3 + 12
        else:
            h = 30
            pg.gradient(M, self.top, cw, h, BRAND_D, BRAND, r=(12, 12, 0, 0))
            pg.text(self.x0, self.top + 19, SCHOOL_MATH, 8, True, "#ffffff", tc=1.4)
            pg.rtext(M + cw - self.PAD, self.top + 19, "LESSON PLAN %s  |  %s (contd.)" % (self.session, day), 8, True, "#ffffff")
            pg.rect(M, self.top + h, cw, 2.5, fill=ACC)
            self.y = self.top + h + 2.5 + 12
        info = self.info

        def post(p, i, n):
            p.line(M + 18, self.bot - 25, M + cw - 18, self.bot - 25, LINE, 0.6)
            p.ctext(PW / 2, self.bot - 11, SCHOOL_FOOT, 8, False, MUTED)
            p.text(M, PH - 14, info, 7.5, False, MUTED)
            p.rtext(PW - M, PH - 14, "Page %d of %d" % (i, n), 7.5, False, MUTED)
        pg.post = post

    def need(self, h):
        if self.y + h > self.limit:
            self.new_page(False)

    def chip(self, x, y, label):
        w = label_width(label) + 13
        self.pg.rect(x, y, w, 12.5, fill=ACC_S, r=3)
        self.pg.rect(x, y, 3, 12.5, fill=ACC, r=1)
        draw_label(self.pg, x + 8, y + 8.6, label)

    def draw_cell(self, x, w, h, lab, ln, tint):
        self.pg.rect(x, self.y, w, h, fill=TINT if tint else "#ffffff", stroke=LINE, lw=0.7, r=7)
        self.chip(x + 8, self.y + 6.5, lab)
        draw_lines(self.pg, ln, x + 9, self.y + 6.5 + 12.5 + 4, self.S, self.LH, INK, BRAND)

    def render(self, f, day, info):
        self.day, self.info = day, info
        self.new_page(True)
        OV = 6.5 + 12.5 + 4 + 6.5
        for kind, specs in MATH_LAYOUT:
            gap = 8
            ws = [(self.bw - 2 * gap) / 3.0] * 3 if kind == "c3" else [(self.bw - gap) / 2.0] * 2 if kind == "c2" else [self.bw]
            built, hs = [], []
            for (lab, key, tint, isl), w in zip(specs, ws):
                v = f.get(key, "")
                ln = list_lines(as_list(v), w - 18, self.S) if isl else text_lines(v, w - 18, self.S)
                built.append(ln)
                hs.append(OV + max(len(ln), 1) * self.LH)
            h = max(hs)
            if kind == "c1" and self.y + h > self.limit:
                lab, key, tint, isl = specs[0]
                ln = built[0]
                k = int((self.limit - self.y - OV) // self.LH)
                if len(ln) >= 4 and k >= 2:
                    if len(ln) - k == 1:
                        k -= 1
                    if k >= 2:
                        self.draw_cell(self.x0, self.bw, OV + k * self.LH, lab, ln[:k], tint)
                        self.new_page(False)
                        built[0] = ln = ln[k:]
                        specs = [(lab.rstrip(":") + " (contd.):", key, tint, isl)]
                        h = OV + len(ln) * self.LH
            self.need(h + 6)
            x = self.x0
            for (lab, key, tint, isl), w, ln in zip(specs, ws, built):
                self.draw_cell(x, w, h, lab, ln, tint)
                x += w + gap
            self.y += h + 6


# ------------------------------------------------------------------ SCIENCE renderer
SB, SD, SL, SBD = "#4a7ab5", "#2f5a8f", "#e6eef8", "#9db1cc"

class SciR:
    M, S, LH = 30, 8.7, 11.6

    def __init__(self, pdf, info):
        self.pdf, self.info = pdf, info
        self.W = PW - 2 * self.M
        self.limit = PH - 46

    def new_page(self, big=False, sub=""):
        pg = self.pdf.add_page()
        self.pg = pg
        M, W = self.M, self.W
        pg.alpha(0.035); pg.rot_text(PW / 2, PH / 2 + 20, "NPS INTERNATIONAL SCHOOL", 30, 52, SD); pg.pop()
        if big:
            h = 96
            pg.gradient(0, 0, PW, h, SD, SB)
            deco_circles(pg, 0, 0, PW, h, 0, [(PW - 50, 8, 80), (PW - 140, 96, 46), (50, 100, 56), (150, -6, 30)])
            pg.ctext(PW / 2, 40, SCHOOL_SCI, 17, True, "#ffffff", tc=1.0)
            pg.ctext(PW / 2, 63, "LESSON PLAN", 11.5, True, "#d8e6f7", tc=3.2)
            pg.rect(0, h, PW, 3, fill="#8fb4de")
            self.y = h + 3 + 16
        else:
            h = 30
            pg.gradient(0, 0, PW, h, SD, SB)
            pg.text(M, 19, SCHOOL_SCI, 8, True, "#ffffff", tc=1.2)
            pg.rtext(PW - M, 19, sub or self.sub, 8, True, "#ffffff")
            pg.rect(0, h, PW, 2.5, fill="#8fb4de")
            self.y = h + 2.5 + 16
        info = self.info

        def post(p, i, n):
            p.line(M, PH - 34, PW - M, PH - 34, "#c9d6e8", 0.7)
            p.text(M, PH - 21, SCHOOL_FOOT + "  |  " + info, 7.5, False, MUTED)
            p.rtext(PW - M, PH - 21, "Page %d of %d" % (i, n), 7.5, False, MUTED)
        pg.post = post

    def need(self, h):
        if self.y + h > self.limit:
            self.new_page(False)

    def heading(self, text, size=11.5, top=14):
        self.need(top + 26)
        self.y += top
        pg = self.pg
        pg.rect(self.M, self.y - 1, 4.5, size + 3, fill=SB, r=1.5)
        pg.text(self.M + 11, self.y + size - 1, text.upper(), size, True, SB)
        pg.line(self.M, self.y + size + 5, PW - self.M, self.y + size + 5, "#c9d6e8", 0.8)
        self.y += size + 13

    def kv(self, y, parts, size=10.5):
        w = sum(tw(t, b, size) for t, b in parts)
        x = PW / 2 - w / 2
        for t, b in parts:
            self.pg.text(x, y, t, size, b, INK if not b else SD)
            x += tw(t, b, size)

    def month_section(self, m):
        self.sub = "LESSON PLAN  |  SUBJECT \u2013 %s, GRADE \u2013 %s" % (clean(m.get("sub")), clean(m.get("gr")))
        self.new_page(True)
        pg = self.pg
        bh = 72
        pg.rect(self.M, self.y, self.W, bh, fill="#f3f7fc", stroke="#c9d6e8", lw=0.8, r=9)
        pg.rect(self.M, self.y, 5, bh, fill=SB, r=(9, 0, 0, 9))
        self.kv(self.y + 20, [("SUBJECT \u2013 ", True), (clean(m.get("sub")) or "______", False), (",   GRADE \u2013 ", True), (clean(m.get("gr")) or "__", False)], 11)
        self.kv(self.y + 40, [("Teacher \u2013 ", True), (clean(m.get("tc")) or "____________", False)], 10)
        self.kv(self.y + 59, [("DATES \u2013 ", True), (clean(m.get("dt")) or "____________", False)], 10)
        self.y += bh
        self.heading("Topics Selected")
        ln = []
        for i, t in enumerate(as_list(m.get("topics"))):
            ls = _wraptok(_tokens(t), self.W - 26, 9.5)
            for j, words in enumerate(ls):
                ln.append(("%d." % (i + 1) if j == 0 else None, 22, _segs(words)))
        if not ln:
            ln = [("1.", 22, [])]
        for one in ln:
            self.need(15)
            self.y = draw_lines(self.pg, [one], self.M + 6, self.y, 9.5, 14.5, INK, SD)
        self.heading("Consolidated Month-wise / Chapter-wise Lesson Plan", 10.5, 12)
        self.table(MROWS, m.get("r") or [])

    def draw_row(self, i, lab, vl, LW, VW):
        ll = _wraptok([(w, True) for w in lab.split()], LW - 16, 7.4)
        h = 10 + max(len(vl) * self.LH, len(ll) * 10.5, self.LH)
        y, pg = self.y, self.pg
        pg.rect(self.M, y, LW, h, fill=SL, stroke=SBD, lw=0.6)
        pg.rect(self.M + LW, y, VW, h, fill="#ffffff" if i % 2 == 0 else "#f9fbfe", stroke=SBD, lw=0.6)
        pg.rect(self.M, y, 3, h, fill=SB)
        for k, words in enumerate(ll):
            pg.text(self.M + 9, y + 5 + 10.5 * k + 7.2, " ".join(w for w, b in words), 7.4, True, SD, tc=0.2)
        draw_lines(pg, vl, self.M + LW + 8, y + 5, self.S, self.LH, INK, SD)
        self.y += h

    def table(self, rows, vals):
        LW = self.W * 0.355
        VW = self.W - LW
        for i, (lab, typ) in enumerate(rows):
            v = vals[i] if i < len(vals) else ""
            vl = list_lines(as_list(v), VW - 16, self.S) if typ in ("l", "r") else text_lines(v, VW - 16, self.S)
            ll = _wraptok([(w, True) for w in lab.split()], LW - 16, 7.4)
            h = 10 + max(len(vl) * self.LH, len(ll) * 10.5, self.LH)
            if self.y + h > self.limit:
                k = int((self.limit - self.y - 10) // self.LH)
                if len(vl) >= 4 and k >= 2:
                    if len(vl) - k == 1:
                        k -= 1
                    if k >= 2:
                        self.draw_row(i, lab, vl[:k], LW, VW)
                        self.new_page(False)
                        lab, vl = lab + " (contd.)", vl[k:]
                self.need(10 + max(len(vl) * self.LH, self.LH))
            self.draw_row(i, lab, vl, LW, VW)

    def day_section(self, n, vals, first):
        self.new_page(False, "LESSON PLAN  |  Day-wise Lesson Transaction")
        pg = self.pg
        if first:
            pg.text(self.M, self.y + 14, "DAY-WISE LESSON TRANSACTION", 15, True, SD, tc=0.6)
            pg.rect(self.M, self.y + 21, 64, 2.5, fill=SB, r=1)
            pg.rect(self.M + 68, self.y + 21.7, self.W - 68, 0.8, fill="#c9d6e8")
            self.y += 36
        lab = "Day %d" % n
        w = tw(lab, True, 11.5) + 34
        pg.gradient(self.M, self.y, w, 24, SD, SB, r=12)
        pg.text(self.M + 17, self.y + 16.5, lab, 11.5, True, "#ffffff")
        self.y += 24 + 9
        self.table(DROWS, vals)


def render_set(st):
    meta = st.get("meta", {})
    if st["kind"] == "math":
        pdf = Pdf(st.get("title", "Lesson Plan"), meta.get("teacher", ""))
        r = MathR(pdf, meta.get("session") or session_for(datetime.date.today()))
        for d in st["docs"]:
            f = d.get("f", {})
            r.render(f, d.get("day", ""), "Class %s \u00b7 Mathematics \u00b7 %s" % (clean(f.get("grade")), clean(f.get("chapter"))[:48]))
        return pdf.build()
    m = st["month"]
    pdf = Pdf(st.get("title", "Lesson Plan"), clean(m.get("tc")))
    r = SciR(pdf, "Class %s \u00b7 %s" % (clean(m.get("gr")), clean(m.get("sub"))))
    r.month_section(m)
    for i, d in enumerate(st.get("days", [])):
        r.day_section(i + 1, d.get("r") or [], i == 0)
    return pdf.build()

def pdf_filename(st):
    meta = st.get("meta", {})
    slug = re.sub(r"[^A-Za-z0-9]+", "-", (meta.get("chapter") or "plan")).strip("-")[:32] or "plan"
    subj = "Maths" if st["kind"] == "math" else "Science"
    return "NPS_%s_Class%s_%s_%s.pdf" % (subj, meta.get("grade", ""), slug, datetime.datetime.now().strftime("%Y%m%d-%H%M"))


# =====================================================================
#  USER INTERFACE (single-page app served to your browser)
# =====================================================================
INDEX_HTML = r'''<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#12335c">
<title>NPS Lesson Planner</title>
<style>
:root{--navy:#12335c;--brand:#1d4e89;--acc:#2eb67d;--accs:#e6f7ef;--sci:#2f5a8f;--sci2:#4a7ab5;--bg:#eef2f8;--card:#fff;--ink:#1f2a44;--muted:#5d6b86;--line:#d5dcea;--tint:#f3f6fb;--sh:0 8px 26px rgba(18,51,92,.11);--inp:#fff}
@media(prefers-color-scheme:dark){:root{--bg:#0d1526;--card:#16213a;--ink:#e8eefb;--muted:#9aa9c7;--line:#2b3b5e;--tint:#1b2845;--sh:0 8px 26px rgba(0,0,0,.4);--inp:#101a31}}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 "Segoe UI",system-ui,-apple-system,Roboto,Arial,sans-serif}
button{font:inherit;color:inherit;cursor:pointer}
#view{max-width:780px;margin:0 auto;padding:0 14px 120px}
.pg{animation:rise .35s ease both}
.sp td.v ul{white-space:normal}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
/* hero */
.hero{margin:0 -14px;padding:calc(env(safe-area-inset-top,0px) + 20px) 20px 78px;background:linear-gradient(135deg,var(--navy),var(--brand) 70%,#2a6db0);color:#fff;border-radius:0 0 36px 36px;position:relative;overflow:hidden}
.hero:before,.hero:after{content:"";position:absolute;border-radius:50%;background:rgba(255,255,255,.07)}
.hero:before{width:260px;height:260px;right:-80px;top:-110px}.hero:after{width:160px;height:160px;left:-60px;bottom:-70px}
.brandrow{display:flex;align-items:center;gap:12px;position:relative;z-index:1}
.logo{width:46px;height:46px;border-radius:50%;background:#fff;color:var(--navy);display:grid;place-items:center;font-weight:900;font-size:14px;letter-spacing:.5px;box-shadow:0 0 0 4px rgba(255,255,255,.22)}
.brandrow small{display:block;opacity:.85;font-size:11.5px;letter-spacing:1.6px;font-weight:700;text-transform:uppercase}
.brandrow b{font-size:19px;letter-spacing:.3px}
.hello{position:relative;z-index:1;margin-top:20px}
.hello h2{margin:0;font-size:25px;font-weight:700}.hello p{margin:2px 0 0;opacity:.85;font-size:13.5px}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:-46px 0 0;position:relative;z-index:2}
.stat{background:var(--card);border-radius:18px;padding:12px 8px;text-align:center;box-shadow:var(--sh)}
.stat b{display:block;font-size:22px;color:var(--brand);line-height:1.1}.stat span{font-size:11.5px;color:var(--muted);font-weight:600}
@media(prefers-color-scheme:dark){.stat b{color:#7fb2ee}}
h3.sec{margin:26px 4px 10px;font-size:13px;letter-spacing:1.6px;text-transform:uppercase;color:var(--muted);font-weight:800}
.subs{display:grid;gap:14px}
@media(min-width:620px){.subs{grid-template-columns:1fr 1fr}}
.sub{border-radius:24px;padding:20px 18px 16px;color:#fff;position:relative;overflow:hidden;box-shadow:var(--sh)}
.sub.m{background:linear-gradient(135deg,#12335c,#1d4e89 60%,#2d7bd0)}.sub.s{background:linear-gradient(135deg,#1f4f86,#2f5a8f 45%,#3aa0a6)}
.sub .ic{position:absolute;right:-6px;top:-8px;font-size:84px;opacity:.16;transform:rotate(12deg)}
.sub h4{margin:0;font-size:21px}.sub p{margin:3px 0 14px;opacity:.88;font-size:13.5px;max-width:80%}
.sub .acts{display:flex;gap:8px;flex-wrap:wrap}
.pill{border:0;border-radius:999px;padding:9px 15px;font-weight:700;font-size:13.5px;background:rgba(255,255,255,.2);color:#fff;backdrop-filter:blur(4px);transition:transform .12s}
.pill.w{background:#fff;color:var(--navy)}.pill:active{transform:scale(.96)}
/* lists & cards */
.card{background:var(--card);border-radius:20px;padding:16px;box-shadow:var(--sh);margin-bottom:12px}
.item{display:flex;align-items:center;gap:12px;background:var(--card);border-radius:18px;padding:12px 14px;margin-bottom:10px;box-shadow:var(--sh)}
.item .bd{width:44px;height:44px;border-radius:14px;display:grid;place-items:center;font-size:22px;flex:none;color:#fff}
.bd.m{background:linear-gradient(135deg,var(--navy),var(--brand))}.bd.s{background:linear-gradient(135deg,var(--sci),#3aa0a6)}
.item .tx{flex:1;min-width:0;cursor:pointer}.item .tx b{display:block;font-size:14.5px;line-height:1.3;overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.item .tx small{color:var(--muted);font-size:12px}
.ib{border:0;background:var(--tint);width:38px;height:38px;border-radius:12px;font-size:17px}
.empty{text-align:center;color:var(--muted);padding:34px 10px}.empty big{display:block;font-size:44px;margin-bottom:6px}
.tip{background:var(--accs);color:#17603f;border-radius:16px;padding:12px 14px;font-size:13px;margin-top:18px}
@media(prefers-color-scheme:dark){.tip{background:#12362b;color:#9be3c0}}
/* page head */
.ph{display:flex;align-items:center;gap:10px;padding:calc(env(safe-area-inset-top,0px) + 14px) 0 10px;position:sticky;top:0;z-index:20;background:var(--bg)}
.ph h2{margin:0;font-size:19px;flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.back{border:0;background:var(--card);width:40px;height:40px;border-radius:14px;box-shadow:var(--sh);font-size:18px}
/* forms */
label.l{display:block;font-size:12px;font-weight:800;letter-spacing:.9px;text-transform:uppercase;color:var(--muted);margin:14px 2px 6px}
input,select,textarea{width:100%;min-width:0;max-width:100%;border:1.5px solid var(--line);background:var(--inp);color:var(--ink);border-radius:14px;padding:12px 13px;font:inherit;outline:none;transition:border .15s,box-shadow .15s}
input:focus,select:focus,textarea:focus{border-color:var(--brand);box-shadow:0 0 0 4px rgba(29,78,137,.14)}
textarea{min-height:92px;resize:vertical}
.g2{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:10px}.g2>*{min-width:0}
.seg{display:flex;background:var(--tint);border-radius:999px;padding:4px;gap:2px}
.seg button{flex:1;border:0;background:none;border-radius:999px;padding:9px 6px;font-weight:700;font-size:13.5px;color:var(--muted)}
.seg button.on{background:linear-gradient(135deg,var(--navy),var(--brand));color:#fff;box-shadow:0 3px 10px rgba(18,51,92,.3)}
.seg.sci button.on{background:linear-gradient(135deg,var(--sci),#3aa0a6)}
.hint{font-size:12px;color:var(--muted);margin:6px 3px 0}
.hol{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.hd{border:1.5px solid var(--line);background:var(--card);border-radius:12px;width:46px;padding:4px 0;text-align:center}
.hd small{display:block;font-size:10px;color:var(--muted);font-weight:700}.hd b{font-size:14px}
.hd.on{background:#fde8e6;border-color:#d9534f;color:#b3382c}.hd.on small{color:#b3382c}
.mini{border:1.5px solid var(--line);background:var(--card);border-radius:999px;padding:6px 12px;font-size:12.5px;font-weight:700;color:var(--brand);margin-right:6px}
.go{width:100%;border:0;border-radius:18px;padding:16px;margin-top:20px;font-weight:800;font-size:16.5px;color:#fff;background:linear-gradient(135deg,var(--acc),#1f9d6b);box-shadow:0 10px 24px rgba(46,182,125,.35);transition:transform .12s}
.go:active{transform:scale(.98)}.go[disabled]{opacity:.6}
.btn{border:0;border-radius:999px;padding:10px 16px;font-weight:700;font-size:13.5px;background:var(--brand);color:#fff;box-shadow:0 3px 10px rgba(18,51,92,.25)}
.btn.alt{background:var(--card);color:var(--brand);border:1.5px solid var(--brand);box-shadow:none}
.btn.red{background:var(--card);color:#c0392b;border:1.5px solid #c0392b;box-shadow:none}
.btn.g{background:linear-gradient(135deg,var(--acc),#1f9d6b);box-shadow:0 4px 14px rgba(46,182,125,.4)}
.bar{display:flex;gap:6px;flex-wrap:nowrap;justify-content:center;padding:6px 0 10px;position:sticky;top:calc(env(safe-area-inset-top,0px) + 64px);z-index:15;background:var(--bg)}
.bar .btn{padding:10px 13px;font-size:13px;white-space:nowrap}
.saved{text-align:center;font-size:12px;color:var(--muted);min-height:16px}
/* nav */
#nav{position:fixed;left:0;right:0;bottom:0;z-index:40;display:flex;justify-content:center;gap:4px;padding:8px 10px calc(env(safe-area-inset-bottom,0px) + 8px);background:var(--card);background:color-mix(in srgb,var(--card) 88%,transparent);backdrop-filter:blur(14px);border-top:1px solid var(--line)}
#nav button{flex:1;max-width:120px;border:0;background:none;border-radius:16px;padding:6px 0;color:var(--muted);font-size:11px;font-weight:700}
#nav button span{display:block;font-size:21px;line-height:1.1}
#nav button.on{color:var(--brand);background:var(--tint)}
@media(prefers-color-scheme:dark){#nav button.on{color:#8fc0f5}}
#toast{position:fixed;left:50%;bottom:92px;transform:translate(-50%,20px);background:#1f2a44;color:#fff;padding:11px 18px;border-radius:999px;font-size:13.5px;font-weight:600;opacity:0;pointer-events:none;transition:.25s;z-index:100;max-width:90%;text-align:center}
#toast.show{opacity:1;transform:translate(-50%,0)}
#modal{position:fixed;inset:0;z-index:90;display:none;align-items:flex-end;justify-content:center;background:rgba(10,20,40,.55);backdrop-filter:blur(3px)}
#modal.show{display:flex}
.mbox{background:var(--card);width:100%;max-width:520px;border-radius:26px 26px 0 0;padding:22px 20px calc(env(safe-area-inset-bottom,0px) + 20px);animation:up .25s ease}
@media(min-width:560px){#modal{align-items:center}.mbox{border-radius:26px}}
@keyframes up{from{transform:translateY(40px);opacity:0}to{transform:none;opacity:1}}
.mbox h4{margin:0 0 6px;font-size:18px}.mbox p{margin:0 0 14px;color:var(--muted);word-break:break-word}
.mbox .mb{display:flex;gap:8px;flex-wrap:wrap}.mbox .mb .btn{flex:1;text-align:center;text-decoration:none;display:block}
/* ---------- Maths card (editor, same look as the PDF) ---------- */
.mp{background:#fff;color:#1f2a44;border-radius:16px;overflow:hidden;box-shadow:var(--sh);margin:16px 0}
.mp-h{background:linear-gradient(135deg,#12335c,#1d4e89);color:#fff;text-align:center;padding:22px 16px 18px;position:relative;overflow:hidden;border-bottom:4px solid #2eb67d}
.mp-h:before{content:"";position:absolute;right:-50px;top:-70px;width:190px;height:190px;border-radius:50%;background:rgba(255,255,255,.07)}
.mp-s{padding:0 30px;font-size:12.5px;letter-spacing:2.2px;font-weight:700;opacity:.92;position:relative}
.mp-h h1{margin:8px 0 4px;font-size:25px;letter-spacing:1px;position:relative}
.mp-day{display:inline-block;margin-top:6px;background:#2eb67d;padding:4px 16px;border-radius:999px;font-weight:700;font-size:15px;position:relative}
.mp-day .f{display:inline-block;min-width:22px;border-bottom:1px dashed rgba(255,255,255,.7)}
.mp-x{position:absolute;top:8px;right:8px;background:rgba(255,255,255,.2);color:#fff;border:0;border-radius:50%;width:30px;height:30px;font-size:14px;z-index:2;line-height:1}
.mp-b{padding:14px}
.mp-meta{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:10px}
.mp-meta .w{grid-column:span 3}
@media(max-width:560px){.mp-meta{grid-template-columns:1fr 1fr}.mp-meta .w{grid-column:span 2}.mp-meta .w3{grid-column:span 2}}
.mp-c{border:1px solid #d5dcea;border-radius:10px;padding:8px 10px;background:#fff;margin-bottom:0}
.mp-r{margin-bottom:10px}.mp-r.t,.mp-pair .mp-c.t{background:#f3f6fb}
.mp-pair{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}
@media(max-width:560px){.mp-pair{grid-template-columns:1fr}}
.lbl{display:inline-block;font-size:11.5px;font-weight:800;letter-spacing:.8px;color:#12335c;background:#e6f7ef;border-left:4px solid #2eb67d;padding:2px 8px;border-radius:4px;margin-bottom:4px}
.f{display:block;min-height:24px;outline:none;font-size:15px;word-break:break-word;white-space:pre-wrap}
.f:focus,.v:focus{background:#fffbe6;border-radius:4px}
.f ul,.v ul{margin:4px 0 2px 18px;padding:0;white-space:normal}.f li{min-height:22px}
.mp-foot{text-align:center;font-size:11px;color:#5d6b86;padding:0 0 14px}
/* ---------- Science doc ---------- */
.sp{background:#fff;color:#1c1c1c;border-radius:14px;box-shadow:var(--sh);margin:16px 0;overflow:hidden}
.sp-ban{background:linear-gradient(135deg,#2f5a8f,#4a7ab5);color:#fff;text-align:center;padding:22px 14px 16px;position:relative;overflow:hidden;border-bottom:4px solid #8fb4de}
.sp-ban:before{content:"";position:absolute;right:-50px;top:-70px;width:190px;height:190px;border-radius:50%;background:rgba(255,255,255,.08)}
.sp-ban .sc{font-size:20px;font-weight:700;letter-spacing:.6px;position:relative}.sp-ban .lp{letter-spacing:4px;font-size:13px;font-weight:700;color:#d8e6f7;margin-top:4px;position:relative}
.sp-in{padding:16px 18px 20px}
.sp-info{text-align:center;line-height:1.75;background:#f3f7fc;border:1px solid #c9d6e8;border-left:5px solid #4a7ab5;border-radius:12px;padding:10px;font-size:15px}
.sp-info b{color:#2f5a8f}
.fill{display:inline-block;min-width:18px;padding:0 4px;outline:none}.fill:empty{border-bottom:1px dotted #9aa8bd}.fill.w:empty{min-width:170px}
h2.sh{color:#4a7ab5;font-size:16px;margin:22px 0 8px;text-transform:uppercase;border-bottom:1px solid #c9d6e8;padding-bottom:5px;display:flex;align-items:center;gap:8px;letter-spacing:.3px}
h2.sh:before{content:"";width:5px;height:18px;border-radius:2px;background:#4a7ab5}
ol.tp{margin:0;padding-left:30px;font-size:15px;line-height:1.7;outline:none}
.sp table{width:100%;border-collapse:collapse;font-size:14px;table-layout:fixed}
.sp td{border:1px solid #9db1cc;padding:5px 10px;line-height:1.45;word-wrap:break-word}
.sp td.lb{width:36%;background:#e6eef8;text-transform:uppercase;font-weight:700;font-size:12px;color:#2f5a8f;border-left:4px solid #4a7ab5;letter-spacing:.2px}
.sp tr:nth-child(even) td.v{background:#f9fbfe}
.sp td.v{white-space:pre-wrap;outline:none}.sp td.v ul{list-style:none;margin:0;padding:0}
.sp td.v li{position:relative;padding-left:13px}.sp td.v li:before{content:"\2022";position:absolute;left:0;color:#4a7ab5}
.sp-days h2{font-size:19px;color:#2f5a8f;text-transform:uppercase;margin:26px 0 4px;padding-top:16px;border-top:3px solid #e6eef8}
.sp-tab{display:flex;align-items:center;justify-content:space-between;margin:14px 0 8px}
.sp-tab span{background:linear-gradient(135deg,#2f5a8f,#4a7ab5);color:#fff;border-radius:999px;padding:5px 18px;font-weight:700}
.sp-tab button{border:1px solid #c0392b;color:#c0392b;background:#fff;border-radius:9px;padding:3px 10px;font-size:12px}
@media(max-width:560px){.sp-in{padding:12px 8px 16px}.sp td{padding:4px 7px;font-size:13px}.sp td.lb{font-size:10.5px;width:34%}}
</style></head>
<body>
<main id="view"></main>
<nav id="nav"></nav>
<div id="toast"></div>
<div id="modal"></div>
<script>
'use strict';
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let DB,INFO,CUR=null,F=null,hol=new Set(),saveT=null,tt=null;
async function api(url,body){
  const r=await fetch(url,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  let j;try{j=await r.json()}catch(e){throw new Error('The app server did not answer')}
  if(!r.ok||j.error)throw new Error(j.error||'Something went wrong');return j;
}
const pad=n=>String(n).padStart(2,'0');
const iso=d=>d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate());
const pd=s=>{const[y,m,d]=s.split('-').map(Number);return new Date(y,m-1,d,12)};
const addDays=(s,n)=>{const d=pd(s);d.setDate(d.getDate()+n);return iso(d)};
const todayISO=()=>iso(new Date());
const range=(a,b)=>{const o=[];if(!a||!b)return o;let d=pd(a);const e=pd(b);while(d<=e&&o.length<400){o.push(iso(d));d.setDate(d.getDate()+1)}return o};
const WK=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
const dmyToIso=s=>{const m=/^(\d\d)\/(\d\d)\/(\d{4})/.exec(s||'');return m?m[3]+'-'+m[2]+'-'+m[1]:null};
const monthEnds=m=>{const[y,mo]=m.split('-').map(Number);return[m+'-01',iso(new Date(y,mo,0,12))]};
const ago=s=>{try{return new Date(s).toLocaleString('en-GB',{day:'numeric',month:'short',hour:'numeric',minute:'2-digit'})}catch(e){return''}};
function toast(m){const t=$('#toast');t.textContent=m;t.classList.add('show');clearTimeout(tt);tt=setTimeout(()=>t.classList.remove('show'),2800)}
function modal(title,msg,btns){
  const M=$('#modal');$('#toast').classList.remove('show');
  M.innerHTML='<div class="mbox"><h4>'+esc(title)+'</h4><p>'+msg+'</p><div class="mb">'+btns.map((b,i)=>b.href?'<a class="btn '+(b.c||'')+'" href="'+b.href+'" '+(b.dl?'download':'')+'>'+esc(b.t)+'</a>':'<button class="btn '+(b.c||'')+'" data-m="'+i+'">'+esc(b.t)+'</button>').join('')+'</div></div>';
  M.classList.add('show');
  M.onclick=e=>{if(e.target===M){M.classList.remove('show');return}const b=e.target.closest('[data-m]');if(!b)return;M.classList.remove('show');const f=btns[+b.dataset.m].fn;if(f)f()};
}
const closeModal=()=>$('#modal').classList.remove('show');
function saveDB(){clearTimeout(saveT);saveT=setTimeout(()=>api('/api/db',DB).catch(()=>toast('Could not save - is the app still running?')),350)}
function go(h){if(location.hash===h)route();else location.hash=h}
const NAV=[['home','\u{1F3E0}','Home'],['new','\u2728','Create'],['library','\u{1F4DA}','Library'],['settings','\u2699\uFE0F','Settings']];
function setView(html,nav){
  $('#view').innerHTML='<div class="pg">'+html+'</div>';
  $('#nav').innerHTML=NAV.map(n=>'<button class="'+(n[0]===nav?'on':'')+'" data-go="#/'+n[0]+'"><span>'+n[1]+'</span>'+n[2]+'</button>').join('');
  window.scrollTo(0,0);
}
const kindIcon=k=>k==='sci'?'\u{1F52C}':'\u{1F4D0}';
const nDays=st=>st.kind==='sci'?(st.days||[]).length:(st.docs||[]).length;
const item=(st,del)=>'<div class="item"><div class="bd '+(st.kind==='sci'?'s':'m')+'">'+kindIcon(st.kind)+'</div><div class="tx" data-go="#/edit/'+st.id+'"><b>'+esc(st.title)+'</b><small>'+nDays(st)+' day'+(nDays(st)===1?'':'s')+(st.kind==='sci'?' + monthly plan':'')+' \u00B7 '+ago(st.updated)+'</small></div><button class="ib" data-pdf="'+st.id+'" title="Export PDF">\u{1F4C4}</button>'+(del?'<button class="ib" data-del="'+st.id+'" title="Delete">\u{1F5D1}\uFE0F</button>':'')+'</div>';

/* ---------------- HOME ---------------- */
function viewHome(){
  const s=DB.settings,lib=DB.library,lessons=lib.reduce((n,x)=>n+nDays(x),0),hr=new Date().getHours();
  const g=hr<12?'Good morning':hr<17?'Good afternoon':'Good evening';
  const sub=(c,k,t,d,ic)=>'<div class="sub '+c+'"><div class="ic">'+ic+'</div><h4>'+t+'</h4><p>'+d+'</p><div class="acts"><button class="pill w" data-go="#/new/'+k+'/single">Single day</button><button class="pill" data-go="#/new/'+k+'/period">Whole period</button></div></div>';
  setView('<section class="hero"><div class="brandrow"><div class="logo">NPS</div><div><small>NPS International School</small><b>Guwahati \u00B7 Lesson Planner</b></div></div><div class="hello"><h2>'+g+', '+esc(s.teacher||'Teacher')+' \u{1F44B}</h2><p>'+new Date().toLocaleDateString('en-GB',{weekday:'long',day:'numeric',month:'long',year:'numeric'})+'</p></div></section>'+
  '<div class="stats"><div class="stat"><b>'+lib.length+'</b><span>Saved plans</span></div><div class="stat"><b>'+lessons+'</b><span>Lessons</span></div><div class="stat"><b>'+esc(INFO.session)+'</b><span>Session</span></div></div>'+
  '<h3 class="sec">Create a lesson plan</h3><div class="subs">'+
  sub('m','math','Mathematics','Daily lesson cards, filled in automatically from your chapter and topic.','\u{1F4D0}')+
  sub('s','sci','Science','Monthly plan plus day-wise tables, with the 5E lesson structure.','\u{1F52C}')+'</div>'+
  '<h3 class="sec">Recent plans</h3>'+(lib.length?lib.slice(0,4).map(x=>item(x)).join(''):'<div class="card empty"><big>\u{1F4DD}</big>Nothing here yet.<br>Pick a subject above and enter a chapter and topic.</div>')+
  (s.teacher?'':'<div class="tip">\u{1F4A1} Add your name in <b>Settings</b> and it will be filled into every lesson plan.</div>')+
  '<div class="tip">\u2705 Works fully offline. PDFs are saved to <b>'+esc(INFO.out_hint)+'</b>.</div>','home');
}

/* ---------------- CREATE ---------------- */
function defForm(){const t=todayISO(),m=t.slice(0,7),e=monthEnds(m);return{subj:'math',mode:'single',grade:'6',chapter:'',topics:'',date:t,rtype:'range',month:m,dfrom:t,dto:addDays(t,4),teacher:DB.settings.teacher||'',minutes:DB.settings.minutes||40}}
function viewNew(a,b){
  if(!F)F=defForm();
  if(a==='math'||a==='sci')F.subj=a;if(b==='single'||b==='period')F.mode=b;
  if(!F.teacher)F.teacher=DB.settings.teacher||'';
  renderNew();
}
function periodRange(){return(F.subj==='math'&&F.rtype==='month')?monthEnds(F.month):[F.dfrom,F.dto]}
function renderNew(){
  const m=F.subj==='math',per=F.mode==='period';
  const rng='<div class="g2"><div><label class="l">From</label><input type="date" data-f="dfrom" value="'+F.dfrom+'"></div><div><label class="l">To</label><input type="date" data-f="dto" value="'+F.dto+'"></div></div>';
  let when;
  if(!per)when='<label class="l">Date</label><input type="date" data-f="date" value="'+F.date+'"><div style="margin-top:8px"><button class="mini" data-act="markhol">Mark this date as a holiday</button></div>';
  else if(m)when='<label class="l">Period</label><div class="seg"><button data-set="rtype:month" class="'+(F.rtype==='month'?'on':'')+'">Whole month</button><button data-set="rtype:range" class="'+(F.rtype==='range'?'on':'')+'">Date range</button></div>'+(F.rtype==='month'?'<label class="l">Month</label><input type="month" data-f="month" value="'+F.month+'">':rng);
  else when='<label class="l">Month</label><input type="month" data-f="month" value="'+F.month+'">'+rng;
  const holBlock=per?'<label class="l">Holidays - tap a date to skip it</label><div><button class="mini" data-act="sundays">All Sundays</button><button class="mini" data-act="clearhol">Clear</button></div><div class="hol" id="hol"></div><p class="hint">Only the dates you tick are skipped. Nothing is skipped automatically.</p>':'';
  setView('<div class="ph"><button class="back" data-go="#/home">\u2190</button><h2>New lesson plan</h2></div><div class="card">'+
  '<label class="l" style="margin-top:2px">Subject</label><div class="seg '+(m?'':'sci')+'"><button data-set="subj:math" class="'+(m?'on':'')+'">\u{1F4D0} Mathematics</button><button data-set="subj:sci" class="'+(m?'':'on')+'">\u{1F52C} Science</button></div>'+
  '<label class="l">Create</label><div class="seg '+(m?'':'sci')+'"><button data-set="mode:single" class="'+(per?'':'on')+'">Single day</button><button data-set="mode:period" class="'+(per?'on':'')+'">Whole period</button></div>'+
  '<label class="l">Class</label><select data-f="grade">'+[1,2,3,4,5,6,7,8,9,10,11,12].map(n=>'<option value="'+n+'" '+(String(n)===String(F.grade)?'selected':'')+'>Class '+n+'</option>').join('')+'</select>'+
  '<label class="l">Name of the chapter</label><input data-f="chapter" list="chl" placeholder="e.g. '+(m?'Fractions':'Light')+'" value="'+esc(F.chapter)+'"><datalist id="chl">'+(DB.history.chapters||[]).map(c=>'<option value="'+esc(c)+'">').join('')+'</datalist>'+
  '<label class="l">Topic / sub-topic</label><textarea data-f="topics" placeholder="'+(m?'Types of fractions':'Reflection of light')+'">'+esc(F.topics)+'</textarea><p class="hint">'+(per?'One topic per line (or separate with ;). Several topics are spread across the days automatically. One topic is taught step by step: introduction, practice, application, revision.':'You can enter more than one topic (one per line) - they are combined into this lesson.')+'</p>'+
  when+holBlock+
  '<div class="g2"><div><label class="l">Teacher</label><input data-f="teacher" placeholder="Your name" value="'+esc(F.teacher)+'"></div><div><label class="l">Period (minutes)</label><input type="number" min="10" max="120" data-f="minutes" value="'+F.minutes+'"></div></div>'+
  '<button class="go" data-act="gen">\u2728 Autofill &amp; generate</button></div>','new');
  if(per)renderHol();
}
function renderHol(){
  const box=$('#hol');if(!box)return;const[a,b]=periodRange(),ds=range(a,b);
  if(!ds.length||ds.length>62){box.innerHTML='<span class="hint">Choose a valid period (up to 62 days) to pick holidays.</span>';return}
  box.innerHTML=ds.map(d=>'<button class="hd '+(hol.has(d)?'on':'')+'" data-hd="'+d+'"><small>'+WK[pd(d).getDay()]+'</small><b>'+d.slice(8)+'</b></button>').join('');
}
async function generate(){
  if(!F.chapter.trim()||!F.topics.trim()){toast('Please enter the chapter and the topic');return}
  const[a,b]=periodRange(),per=F.mode==='period',inR=new Set(range(a,b));
  const btn=$('.go');btn.disabled=true;btn.textContent='Writing your lesson plan\u2026';
  try{
    const p={subject:F.subj,mode:F.mode,grade:F.grade,chapter:F.chapter,topics:F.topics,teacher:F.teacher,minutes:F.minutes,session:DB.settings.session,
      date:F.date,month:F.month,range_type:F.rtype,dfrom:F.dfrom,dto:F.dto,holidays:per?[...hol].filter(d=>inR.has(d)):[]};
    const st=await api('/api/autofill',p);
    if(per){DB.holidays=[...new Set([...(DB.holidays||[]).filter(d=>!inR.has(d)),...p.holidays])].sort()}
    if(!DB.settings.teacher&&F.teacher)DB.settings.teacher=F.teacher;
    const H=DB.history;H.chapters=[F.chapter.trim(),...(H.chapters||[]).filter(c=>c!==F.chapter.trim())].slice(0,40);
    DB.library.unshift(st);DB.library=DB.library.slice(0,200);saveDB();F.chapter='';F.topics='';
    toast('Lesson plan ready \u2728 - edit anything you like');go('#/edit/'+st.id);
  }catch(e){toast(e.message);btn.disabled=false;btn.textContent='\u2728 Autofill & generate'}
}

/* ---------------- EDITOR (same layout as the school formats) ---------------- */
const fv=(f,k)=>f[k]==null?'':f[k];
const fld=(i,k,f)=>'<div class="f" contenteditable="true" data-d="'+i+'" data-k="'+k+'">'+esc(fv(f,k))+'</div>';
const lst=(i,k,f)=>{const a=Array.isArray(f[k])?f[k]:[];return'<div class="f" contenteditable="true" data-d="'+i+'" data-k="'+k+'" data-l="1"><ul>'+(a.length?a:['']).map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul></div>'};
const mc=(cls,lbl,body)=>'<div class="mp-c '+cls+'"><span class="lbl">'+lbl+'</span>'+body+'</div>';
function mathDoc(d,i){
  const f=d.f,sess=CUR.meta.session;
  return'<article class="mp"><header class="mp-h"><button class="mp-x" data-act="rm" data-i="'+i+'" title="Remove this day">\u2715</button><div class="mp-s">NPS INTERNATIONAL SCHOOL GUWAHATI</div><h1>LESSON PLAN '+esc(sess)+'</h1><div class="mp-day">Day \u2013 <span class="f" contenteditable="true" data-d="'+i+'" data-day="1">'+esc(d.day)+'</span></div></header><div class="mp-b">'+
  '<div class="mp-meta">'+mc('','SUBJECT:',fld(i,'subject',f))+mc('','GRADE:',fld(i,'grade',f))+mc('w3','TEACHER:',fld(i,'teacher',f))+
  mc('w','NAME OF THE CHAPTER:',fld(i,'chapter',f))+mc('w','TOPIC/SUB-TOPIC:',fld(i,'topic',f))+
  mc('w3','TIME:',fld(i,'time',f))+mc('','DATE FROM:',fld(i,'dfrom',f))+mc('','DATE TO:',fld(i,'dto',f))+'</div>'+
  mc('mp-r','LEARNING OBJECTIVE:',fld(i,'objective',f))+
  '<div class="mp-pair">'+mc('t','21<sup>ST</sup> CENTURY SKILLS:',fld(i,'skills',f))+mc('t','COMPETENCIES INCORPORATED:',fld(i,'competencies',f))+'</div>'+
  '<div class="mp-pair">'+mc('','STRATEGIES USED:',fld(i,'strategies',f))+mc('','RESOURCES USED',fld(i,'resources',f))+'</div>'+
  mc('mp-r t','WARM UP ACTIVITY:',fld(i,'warmup',f))+mc('mp-r','PROCEDURE:',lst(i,'procedure',f))+
  '<div class="mp-pair">'+mc('t','INTERDISCIPLINARY INTEGRATION:',fld(i,'interdisc',f))+mc('t','SDG:',fld(i,'sdg',f))+'</div>'+
  mc('mp-r','WRAP ACITVITY:',fld(i,'wrap',f))+mc('mp-r','ASSESSMENT:',fld(i,'assessment',f))+mc('mp-r','LEARNING OUTCOMES:',lst(i,'outcomes',f))+mc('mp-r t','HOME ASSIGNMENT:',fld(i,'homework',f))+
  '</div><div class="mp-foot">NPS International School Guwahati</div></article>';
}
function sciRows(defs,vals,d){
  return defs.map((df,i)=>{const v=vals[i],isl=df[1]==='l'||df[1]==='r';
    const body=isl?'<ul>'+((Array.isArray(v)&&v.length)?v:['']).map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':esc(Array.isArray(v)?v.join('\n'):v);
    return'<tr><td class="lb">'+esc(df[0])+'</td><td class="v" contenteditable="true" data-d="'+d+'" data-r="'+i+'"'+(isl?' data-l="1"':'')+'>'+body+'</td></tr>'}).join('');
}
function sciDoc(){
  const m=CUR.month,fill=(k,w)=>'<span class="fill '+(w||'')+'" contenteditable="true" data-m="'+k+'">'+esc(m[k])+'</span>';
  return'<article class="sp"><div class="sp-ban"><div class="sc">NPS INTERNATIONAL SCHOOL, GUWAHATI</div><div class="lp">LESSON PLAN</div></div><div class="sp-in">'+
  '<div class="sp-info"><b>SUBJECT \u2013 </b>'+fill('sub')+', <b>GRADE \u2013 </b>'+fill('gr')+'<br><b>Teacher \u2013 </b>'+fill('tc','w')+'<br><b>DATES \u2013 </b>'+fill('dt','w')+'</div>'+
  '<h2 class="sh">Topics Selected</h2><ol class="tp" contenteditable="true" data-topics="1">'+((m.topics&&m.topics.length)?m.topics:['']).map(t=>'<li>'+esc(t)+'</li>').join('')+'</ol>'+
  '<h2 class="sh">Consolidated Month-wise / Chapter-wise Lesson Plan</h2><table>'+sciRows(INFO.mrows,m.r,'m')+'</table>'+
  '<div class="sp-days"><h2>Day-wise Lesson Transaction</h2>'+CUR.days.map((d,i)=>'<div class="sp-tab"><span>Day '+(i+1)+'</span><button data-act="rmday" data-i="'+i+'">Remove day</button></div><table>'+sciRows(INFO.drows,d.r,i)+'</table>').join('')+'</div></div></article>';
}
function viewEdit(id){
  CUR=DB.library.find(x=>x.id===id);if(!CUR){toast('Plan not found');go('#/library');return}
  setView('<div class="ph"><button class="back" data-go="#/library">\u2190</button><h2>'+esc(CUR.title)+'</h2></div><div class="bar"><button class="btn alt" data-act="regen">\u21BB Refill</button><button class="btn alt" data-act="addday">\uFF0B Day</button><button class="btn g" data-act="pdf">\u{1F4C4} Export PDF</button></div><div class="saved" id="saved">Auto-saved \u00B7 tap any text to edit</div>'+
  (CUR.kind==='math'?CUR.docs.map(mathDoc).join(''):sciDoc()),'library');
}
const val=el=>{if(el.dataset.l){let a=$$('li',el).map(l=>l.innerText.trim()).filter(Boolean);if(!a.length)a=el.innerText.split('\n').map(s=>s.trim()).filter(Boolean);return a}return el.innerText.replace(/\n+$/,'')};
function touch(){CUR.updated=new Date().toISOString().slice(0,19);saveDB();const s=$('#saved');if(s)s.textContent='Saved \u2713'}
document.addEventListener('input',e=>{
  const t=e.target;
  if(t.dataset&&t.dataset.f!==undefined){F[t.dataset.f]=t.value;return}
  if(!CUR||!t.closest)return;const el=t.closest('[contenteditable]');if(!el)return;const D=el.dataset;
  if(D.k!==undefined)CUR.docs[+D.d].f[D.k]=val(el);
  else if(D.day!==undefined)CUR.docs[+D.d].day=el.innerText.trim();
  else if(D.r!==undefined)(D.d==='m'?CUR.month.r:CUR.days[+D.d].r)[+D.r]=val(el);
  else if(D.m!==undefined)CUR.month[D.m]=el.innerText.trim();
  else if(D.topics!==undefined)CUR.month.topics=$$('li',el).map(l=>l.innerText.trim()).filter(Boolean);
  else return;
  touch();
});
document.addEventListener('change',e=>{
  const t=e.target;if(!t.dataset||t.dataset.f===undefined)return;
  if(t.dataset.f==='month'&&F.subj==='sci'){const[a,b]=monthEnds(t.value);F.dfrom=a;F.dto=b;renderNew()}
  if(['dfrom','dto','month'].includes(t.dataset.f))renderHol();
});
document.addEventListener('paste',e=>{const el=e.target.closest&&e.target.closest('[contenteditable]');if(!el)return;e.preventDefault();document.execCommand('insertText',false,(e.clipboardData||window.clipboardData).getData('text/plain'))});

/* ---------------- actions ---------------- */
async function exportPdf(st){
  toast('Creating your PDF\u2026');
  try{
    const r=await api('/api/pdf',st);
    modal('\u2705 PDF created','<b>'+esc(r.name)+'</b><br>'+(r.shared?'Saved in your phone\u2019s <b>Downloads \u203A NPS_Lesson_Plans</b> folder.':'Saved inside Termux. Tap <b>Download</b> to keep a copy on your phone (run <code>termux-setup-storage</code> once to save straight to Downloads).')+'<br><small>'+esc(r.path)+'</small>',
      [{t:'Open PDF',c:'g',fn:()=>api('/api/open',{name:r.name}).catch(e=>toast(e.message+' - use Download instead'))},{t:'Download',c:'alt',href:r.url+'?dl=1',dl:1},{t:'Close',c:'alt'}]);
    if(!r.shared)setTimeout(()=>{const a=document.createElement('a');a.href=r.url+'?dl=1';a.download=r.name;document.body.appendChild(a);a.click();a.remove()},500);
  }catch(e){toast(e.message)}
}
async function regen(){
  try{const st=await api('/api/autofill',Object.assign({},CUR.params,{seed:(CUR.params.seed||0)+1}));
    st.id=CUR.id;st.created=CUR.created;const i=DB.library.findIndex(x=>x.id===CUR.id);DB.library[i]=st;saveDB();viewEdit(st.id);toast('Filled again with a fresh variation')}catch(e){toast(e.message)}
}
async function addDay(){
  const last=CUR.kind==='math'?CUR.docs[CUR.docs.length-1].f.dto:CUR.days[CUR.days.length-1].r[0];
  const next=addDays(dmyToIso(last)||todayISO(),1),tp=CUR.meta.topics;
  try{const st=await api('/api/autofill',{subject:CUR.kind,mode:'single',grade:CUR.meta.grade,chapter:CUR.meta.chapter,topics:tp[tp.length-1],teacher:CUR.meta.teacher,minutes:CUR.meta.minutes,date:next,phase:'practice',seed:CUR.docs?CUR.docs.length:CUR.days.length,session:CUR.meta.session});
    if(CUR.kind==='math'){const d=st.docs[0];d.day=CUR.docs.length+1;CUR.docs.push(d)}else CUR.days.push(st.days[0]);
    touch();viewEdit(CUR.id);toast('Day added')}catch(e){toast(e.message)}
}
function rmDay(i){
  modal('Remove this day?','This day will be removed from the plan.',[{t:'Remove',c:'red',fn:()=>{
    if(CUR.kind==='math'){CUR.docs.splice(i,1);CUR.docs.forEach((d,k)=>d.day=k+1)}else CUR.days.splice(i,1);touch();viewEdit(CUR.id)}},{t:'Keep',c:'alt'}]);
}
document.addEventListener('click',e=>{
  const t=e.target.closest('[data-go],[data-act],[data-pdf],[data-del],[data-set],[data-hd],[data-rmhol]');if(!t)return;
  const D=t.dataset;
  if(D.go){go(D.go);return}
  if(D.pdf){const st=DB.library.find(x=>x.id===D.pdf);if(st)exportPdf(st);return}
  if(D.del){modal('Delete this plan?','It will be removed from your library.',[{t:'Delete',c:'red',fn:()=>{DB.library=DB.library.filter(x=>x.id!==D.del);saveDB();route()}},{t:'Keep',c:'alt'}]);return}
  if(D.set){const[k,v]=D.set.split(':');F[k]=v;renderNew();return}
  if(D.hd){hol.has(D.hd)?hol.delete(D.hd):hol.add(D.hd);t.classList.toggle('on');return}
  if(D.rmhol){DB.holidays=DB.holidays.filter(x=>x!==D.rmhol);saveDB();viewSettings();return}
  const a=D.act;
  if(a==='gen')generate();
  else if(a==='sundays'){const[x,y]=periodRange();range(x,y).forEach(d=>{if(pd(d).getDay()===0)hol.add(d)});renderHol()}
  else if(a==='clearhol'){const[x,y]=periodRange();range(x,y).forEach(d=>hol.delete(d));renderHol()}
  else if(a==='markhol'){DB.holidays=[...new Set([...(DB.holidays||[]),F.date])].sort();hol.add(F.date);saveDB();toast('Recorded as a holiday - no lesson plan is created for it')}
  else if(a==='pdf')exportPdf(CUR);
  else if(a==='regen')modal('Fill again?','The lesson text will be replaced with a fresh autofill. Your edits on this plan will be lost.',[{t:'Fill again',c:'g',fn:regen},{t:'Cancel',c:'alt'}]);
  else if(a==='addday')addDay();
  else if(a==='rm'||a==='rmday')rmDay(+D.i);
  else if(a==='savecfg'){DB.settings.teacher=$('#s_t').value.trim();DB.settings.minutes=Math.max(10,Math.min(120,+$('#s_m').value||40));DB.settings.session=$('#s_s').value.trim();if(F){F.teacher=DB.settings.teacher;F.minutes=DB.settings.minutes}saveDB();api('/api/info').then(i=>{INFO=i;toast('Settings saved \u2713');viewSettings()})}
});

/* ---------------- LIBRARY & SETTINGS ---------------- */
function viewLib(){
  const q=($('#q')&&$('#q').value||'').toLowerCase();
  setView('<div class="ph"><h2>\u{1F4DA} My library</h2></div><input id="q" placeholder="Search by chapter, class or subject\u2026" oninput="libFilter()">'+'<div id="lib" style="margin-top:12px"></div>','library');libFilter();
}
function libFilter(){
  const q=($('#q').value||'').toLowerCase(),L=DB.library.filter(x=>!q||x.title.toLowerCase().includes(q));
  $('#lib').innerHTML=L.length?L.map(x=>item(x,1)).join(''):'<div class="card empty"><big>\u{1F4DA}</big>'+(DB.library.length?'No plans match your search.':'Your saved plans will appear here.')+'</div>';
}
function viewSettings(){
  const s=DB.settings,H=(DB.holidays||[]).slice().sort();
  setView('<div class="ph"><h2>\u2699\uFE0F Settings</h2></div><div class="card"><label class="l" style="margin-top:0">Teacher name</label><input id="s_t" value="'+esc(s.teacher)+'" placeholder="Filled into every lesson plan">'+
  '<div class="g2"><div><label class="l">Default period (min)</label><input id="s_m" type="number" min="10" max="120" value="'+(s.minutes||40)+'"></div><div><label class="l">Session</label><input id="s_s" value="'+esc(s.session)+'" placeholder="'+esc(INFO.session_auto)+'"></div></div>'+
  '<p class="hint">Session is shown in the header, e.g. LESSON PLAN '+esc(INFO.session)+'. Leave it empty to follow the academic year automatically.</p><button class="go" data-act="savecfg">Save settings</button></div>'+
  '<h3 class="sec">Remembered holidays</h3><div class="card">'+(H.length?H.map(d=>'<button class="mini" data-rmhol="'+d+'">'+d.split('-').reverse().join('/')+' \u2715</button>').join(' '):'<span class="hint">None yet. Dates you mark as holidays are remembered here.</span>')+'</div>'+
  '<h3 class="sec">About</h3><div class="card"><b>NPS Lesson Planner</b><p class="hint" style="margin-top:4px">Offline autofill for Class 1\u201312, Mathematics and Science (CBSE / NCERT). Autofill is rule-based, so treat each plan as a strong first draft and review it before use.<br><br>PDF folder: <b>'+esc(INFO.out_dir)+'</b></p></div>','settings');
}
function route(){
  closeModal();const h=(location.hash||'#/home').slice(2).split('/'),p=h[0];
  if(p==='new')viewNew(h[1],h[2]);else if(p==='edit')viewEdit(h[1]);else if(p==='library')viewLib();else if(p==='settings')viewSettings();else viewHome();
}
(async function(){
  try{[DB,INFO]=await Promise.all([api('/api/db'),api('/api/info')])}catch(e){document.body.innerHTML='<p style="padding:30px;font-family:sans-serif">Cannot reach the app. Make sure it is still running in Termux.</p>';return}
  DB.history=DB.history||{chapters:[]};DB.holidays=DB.holidays||[];DB.library=DB.library||[];hol=new Set(DB.holidays);
  addEventListener('hashchange',route);route();
})();
</script></body></html>
'''


# =====================================================================
#  LOCAL SERVER  (127.0.0.1 only - nothing leaves your phone)
# =====================================================================
from urllib.parse import quote

def app_info():
    d, shared = out_dirs()
    s = db_load().get("settings", {})
    auto = session_for(datetime.date.today())
    return {"version": "1.0", "shared": shared, "out_dir": d,
            "out_hint": "Downloads \u203a NPS_Lesson_Plans" if shared else d,
            "session": (s.get("session") or "").strip() or auto, "session_auto": auto,
            "mrows": [[l, t] for l, t in MROWS], "drows": [[l, t] for l, t in DROWS]}

class Handler(BaseHTTPRequestHandler):
    server_version = "NPSPlanner/1.0"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _host_ok(self):
        return (self.headers.get("Host", "").split(":")[0] or "") in ("127.0.0.1", "localhost")

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "forbidden"})
        u = urlparse(self.path)
        try:
            if u.path in ("/", "/index.html"):
                return self._send(200, INDEX_HTML, "text/html; charset=utf-8")
            if u.path == "/api/db":
                return self._send(200, db_load())
            if u.path == "/api/info":
                return self._send(200, app_info())
            if u.path.startswith("/files/"):
                name = unquote(u.path[7:])
                p = find_pdf(name)
                if not p:
                    return self._send(404, {"error": "File not found"})
                with open(p, "rb") as f:
                    data = f.read()
                disp = "attachment" if "dl=1" in (u.query or "") else "inline"
                return self._send(200, data, "application/pdf", {"Content-Disposition": '%s; filename="%s"' % (disp, name)})
            if u.path == "/favicon.ico":
                return self._send(204, b"", "image/x-icon")
            return self._send(404, {"error": "Not found"})
        except Exception as e:
            return self._send(500, {"error": str(e)})

    def do_POST(self):
        if not self._host_ok():
            return self._send(403, {"error": "forbidden"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 30 * 1024 * 1024:
                return self._send(413, {"error": "Too large"})
            data = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            path = urlparse(self.path).path
            if path == "/api/db":
                db_save(data)
                return self._send(200, {"ok": True})
            if path == "/api/autofill":
                return self._send(200, autofill(data))
            if path == "/api/pdf":
                if data.get("kind") not in ("math", "sci"):
                    raise ValueError("Unknown plan type")
                pdf = render_set(data)
                d, shared = out_dirs()
                name = pdf_filename(data)
                full = os.path.join(d, name)
                with open(full, "wb") as f:
                    f.write(pdf)
                return self._send(200, {"name": name, "path": full, "shared": shared, "url": "/files/" + quote(name), "bytes": len(pdf)})
            if path == "/api/open":
                p = find_pdf(data.get("name"))
                if not p:
                    raise ValueError("File not found")
                if os.environ.get("NPS_ANDROID_APP") == "1":
                    hook = globals().get("_android_export_pdf")
                    if not hook:
                        raise ValueError("Android PDF viewer is not ready")
                    hook(p, open_after=True)
                else:
                    try:
                        subprocess.Popen(["termux-open", "--content-type", "application/pdf", p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except FileNotFoundError:
                        raise ValueError("termux-open is not available")
                return self._send(200, {"ok": True})
            return self._send(404, {"error": "Not found"})
        except ValueError as e:
            return self._send(400, {"error": str(e)})
        except Exception as e:
            traceback.print_exc()
            return self._send(500, {"error": "Unexpected error: %s" % e})

def _running(port):
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:%d/api/info" % port, timeout=0.8) as r:
            return b"mrows" in r.read()
    except Exception:
        return False

def _run(cmd):
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

def main():
    port, openbrowser = 8765, True
    a = sys.argv[1:]
    if "--port" in a:
        port = int(a[a.index("--port") + 1])
    if "--no-open" in a:
        openbrowser = False
    if _running(port):
        url = "http://127.0.0.1:%d/" % port
        print("\n  %s is already running -> %s\n" % (APP_NAME, url))
        if openbrowser:
            _run(["termux-open-url", url])
        return
    srv = None
    for p in range(port, port + 20):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", p), Handler)
            srv.daemon_threads = True
            port = p
            break
        except OSError:
            continue
    if not srv:
        print("Could not start: no free port found.")
        return
    url = "http://127.0.0.1:%d/" % port
    d, shared = out_dirs()
    line = "=" * 56
    print("\n" + line)
    print("  %s  -  NPS International School Guwahati" % APP_NAME)
    print(line)
    print("  App address : %s" % url)
    print("  PDFs saved  : %s" % d)
    if not shared:
        print("  (tip) run  termux-setup-storage  once so PDFs appear in Downloads)")
    print("  Stop the app: press CTRL + C")
    print(line + "\n")
    _run(["termux-wake-lock"])
    if openbrowser:
        threading.Timer(0.8, lambda: _run(["termux-open-url", url])).start()
        print("  Opening your browser... if it does not open, copy the address above.\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _run(["termux-wake-unlock"])
        print("\n  App stopped. Your plans are saved. Bye!\n")

if __name__ == "__main__":
    main()
