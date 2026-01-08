import os
import re
import sys
import json
import time
import random
import string
import hashlib
from pathlib import Path
from io import BytesIO
from typing import Dict, Optional, Tuple, Any
from urllib.parse import urlparse, parse_qs

try:
    import httpx
except ImportError:
    print("Error: httpx diperlukan. Install: pip install httpx")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Error: requests diperlukan. Install: pip install requests")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Error: Pillow diperlukan. Install: pip install Pillow")
    sys.exit(1)

# ============ CONFIG ============
PROGRAM_ID = "68d47554aa292d20b9bec8f7"
SHEERID_BASE_URL = "https://services.sheerid.com"

# ============ EMAIL TEMPORARY SERVICE ============
GUERRILLA_MAIL_API = "https://api.guerrillamail.com/ajax.php"
GUERRILLA_DOMAINS = [
    "sharklasers.com",         
    "guerrillamail.com",      
    "guerrillamail.info",      
    "grr.la",                 
    "guerrillamail.biz",        
    "guerrillamail.de",        
    "guerrillamail.net",       
    "guerrillamail.org",      
    "guerrillamailblock.com",  
    "pokemail.net",            
    "spam4.me",                
    "guerrillamail.fr",         
    "guerrillamail.nl",         
]

class TempEmailService:
    """Class untuk mengelola email temporary menggunakan API Guerrilla Mail"""
    
    def __init__(self, proxy_config=None, verification_session=None, email_address=None):
        """
        Args:
            email_address: Jika diberikan, gunakan email ini (manual input)
        """
        self.email_address = email_address
        self.email_token = None
        self.session = requests.Session()
        self.verification_session = verification_session  # Session dari httpx untuk verifikasi
        
        if proxy_config:
            self.session.proxies = proxy_config
        
        # Jika email diberikan secara manual, tandai sebagai manual input
        self.is_manual_email = email_address is not None
    
    def generate_email(self):
        """Mendapatkan alamat email (otomatis atau manual)"""
        if self.email_address:  # Jika sudah ada (manual input)
            print(f"   [EMAIL] Using manual email: {self.email_address}")
            return self.email_address
        
        try:
            domain = random.choice(GUERRILLA_DOMAINS)
            params = {
                'f': 'get_email_address',
                'domain': domain
            }
            
            resp = self.session.get(GUERRILLA_MAIL_API, params=params, timeout=30)
            
            if resp.status_code == 200:
                data = resp.json()
                self.email_address = data.get('email_addr')
                self.email_token = data.get('sid_token')
                
                if self.email_address and self.email_token:
                    print(f"   [EMAIL] Generated: {self.email_address}")
                    return self.email_address
        except Exception as e:
            print(f"   [EMAIL ERROR] API failed: {e}")
        
        # Fallback: generate manual
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        domain = random.choice(GUERRILLA_DOMAINS)
        self.email_address = f"{username}@{domain}"
        print(f"   [EMAIL] Manual fallback: {self.email_address}")
        return self.email_address
    
    def check_for_verification_link(self, max_checks=15, delay=5):
        """Memeriksa inbox untuk link verifikasi dan OTOMATIS klik"""
        # Jika email manual, tidak bisa akses inbox
        if self.is_manual_email:
            print(f"   [EMAIL] Manual email: {self.email_address}")
            print(f"   [EMAIL] Cannot check inbox for manual email")
            print(f"   [EMAIL] Please check your email manually for verification link")
            return None
            
        if not self.email_token:
            return None
        
        print(f"   [EMAIL] Checking inbox for verification link...")
        print(f"   [EMAIL] Will auto-click link if found")
        
        for i in range(max_checks):
            print(f"   [EMAIL] Check {i+1}/{max_checks}...")
            time.sleep(delay)
            
            try:
                params = {
                    'f': 'get_email_list',
                    'sid_token': self.email_token,
                    'offset': 0
                }
                
                resp = self.session.get(GUERRILLA_MAIL_API, params=params, timeout=15)
                
                if resp.status_code == 200:
                    data = resp.json()
                    emails = data.get('list', [])
                    
                    for email in emails:
                        mail_id = email.get('mail_id')
                        mail_from = email.get('mail_from', '').lower()
                        mail_subject = email.get('mail_subject', '').lower()
                        
                        # Cek jika email dari SheerID
                        if 'sheerid' in mail_from or 'verif' in mail_subject or 'confirm' in mail_subject:
                            print(f"   [EMAIL] Found verification email (ID: {mail_id})")
                            
                            # Ekstrak dan klik link
                            if self._auto_click_verification_link(mail_id):
                                print(f"   [EMAIL] SUCCESS: Link clicked automatically!")
                                return "AUTO_CLICKED"
                            else:
                                # Kembalikan link manual
                                link = self._extract_link_from_email(mail_id)
                                if link:
                                    return link
                
            except Exception as e:
                print(f"   [EMAIL ERROR] Check failed: {e}")
                continue
        
        print(f"   [EMAIL] No verification link found after {max_checks} checks")
        return None
    
    def _auto_click_verification_link(self, mail_id):
        """OTOMATIS klik link verifikasi dari email"""
        try:
            # 1. Dapatkan konten email
            params = {
                'f': 'fetch_email',
                'sid_token': self.email_token,
                'email_id': mail_id
            }
            
            resp = self.session.get(GUERRILLA_MAIL_API, params=params, timeout=15)
            if resp.status_code != 200:
                return False
            
            data = resp.json()
            content = data.get('mail_body', '') + " " + data.get('mail_subject', '')
            
            # 2. Ekstrak link verifikasi
            import re
            link = None
            
            # Pattern 1: Link lengkap
            patterns = [
                r'https://services\.sheerid\.com[^\s<>"]+',
                r'https://verify\.sheerid\.com[^\s<>"]+',
                r'https://[^\s<>"]*sheerid[^\s<>"]*verif[^\s<>"]*',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    link = matches[0]
                    # Bersihkan link
                    link = link.replace('&amp;', '&')
                    link = link.replace('\\/', '/')
                    break
            
            if not link:
                # Pattern 2: Cari token dan bangun link
                token_patterns = [
                    r'emailToken=(\d+)',
                    r'token=(\d+)',
                    r'verificationId=([a-f0-9]+)'
                ]
                
                for pattern in token_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        token = matches[0]
                        if 'emailToken' in pattern or 'token' in pattern:
                            link = f"https://services.sheerid.com/verify/68d47554aa292d20b9bec8f7/?emailToken={token}"
                        else:
                            link = f"https://services.sheerid.com/verify/68d47554aa292d20b9bec8f7/?verificationId={token}"
                        break
            
            if not link:
                return False
            
            print(f"   [EMAIL] Found link: {link[:80]}...")
            
            # 3. Klik link menggunakan session yang sama
            # Gunakan session dari httpx client jika ada
            if self.verification_session:
                try:
                    response = self.verification_session.get(link, timeout=10)
                    print(f"   [EMAIL] Auto-click status: {response.status_code}")
                    
                    if response.status_code == 200:
                        # Cek jika verifikasi berhasil
                        if "verified" in response.text.lower() or "success" in response.text.lower():
                            print(f"   [EMAIL] VERIFICATION SUCCESS via auto-click!")
                            return True
                        else:
                            print(f"   [EMAIL] Page loaded, checking status...")
                            return True
                    else:
                        print(f"   [EMAIL] Auto-click failed: Status {response.status_code}")
                except Exception as e:
                    print(f"   [EMAIL] Auto-click error: {e}")
            
            # 4. Jika tidak ada session, gunakan requests session
            try:
                response = self.session.get(link, timeout=10)
                print(f"   [EMAIL] Auto-click (requests) status: {response.status_code}")
                
                if response.status_code == 200:
                    print(f"   [EMAIL] Link clicked successfully")
                    return True
            except Exception as e:
                print(f"   [EMAIL] Requests auto-click error: {e}")
            
            return False
                
        except Exception as e:
            print(f"   [EMAIL ERROR] Auto-click failed: {e}")
            return False
    
    def _extract_link_from_email(self, mail_id):
        """Ekstrak link dari email (manual)"""
        try:
            params = {
                'f': 'fetch_email',
                'sid_token': self.email_token,
                'email_id': mail_id
            }
            
            resp = self.session.get(GUERRILLA_MAIL_API, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get('mail_body', '') + " " + data.get('mail_subject', '')
                
                # Cari link verifikasi
                import re
                patterns = [
                    r'https://services\.sheerid\.com[^\s<>"]+',
                    r'verificationId=[a-f0-9]+',
                    r'emailToken=\d+'
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        if 'http' in match:
                            # Bersihkan link
                            link = match.replace('&amp;', '&')
                            link = link.replace('\\/', '/')
                            return link
                        elif 'verificationId=' in match:
                            return f"https://services.sheerid.com/verify/68d47554aa292d20b9bec8f7/?{match}"
                        elif 'emailToken=' in match:
                            return f"https://services.sheerid.com/verify/68d47554aa292d20b9bec8f7/?{match}"
                        
        except Exception as e:
            print(f"   [EMAIL ERROR] Failed to extract link: {e}")
        
        return None

# ============ K12 SCHOOLS (VALID IDs) ============
K12_SCHOOLS = [
    # Sekolah yang benar-benar ada di database SheerID
    {"id": 3521141, "name": "Walter Payton College Preparatory High School", "city": "Chicago, IL", "weight": 100},
    {"id": 3521074, "name": "Whitney M Young Magnet High School", "city": "Chicago, IL", "weight": 98},
    {"id": 219471, "name": "Northside College Preparatory High School", "city": "Chicago, IL", "weight": 95},
    {"id": 219254, "name": "Lane Technical High School", "city": "Chicago, IL", "weight": 90},
    
    # NYC Specialized High Schools
    {"id": 155694, "name": "Stuyvesant High School", "city": "New York, NY", "weight": 100},
    {"id": 156251, "name": "Bronx High School Of Science", "city": "Bronx, NY", "weight": 98},
    {"id": 157582, "name": "Brooklyn Technical High School", "city": "Brooklyn, NY", "weight": 95},
    {"id": 155770, "name": "Staten Island Technical High School", "city": "Staten Island, NY", "weight": 90},
    {"id": 158162, "name": "Townsend Harris High School", "city": "Flushing, NY", "weight": 88},
    
    # Virginia / DC STEM
    {"id": 3704245, "name": "Thomas Jefferson High School For Science And Technology", "city": "Alexandria, VA", "weight": 100},
    {"id": 167407, "name": "McKinley Technology High School", "city": "Washington, DC", "weight": 85},
    
    # California Elite
    {"id": 3539252, "name": "Gretchen Whitney High School", "city": "Cerritos, CA", "weight": 95},
    {"id": 262338, "name": "Lowell High School (San Francisco)", "city": "San Francisco, CA", "weight": 90},
    {"id": 262370, "name": "Palo Alto High School", "city": "Palo Alto, CA", "weight": 88},
    {"id": 262410, "name": "Gunn (Henry M.) High School", "city": "Palo Alto, CA", "weight": 85},
    
    # BASIS Charter Network (real IDs)
    {"id": 3536914, "name": "BASIS Scottsdale", "city": "Scottsdale, AZ", "weight": 90},
    {"id": 250527, "name": "BASIS Tucson North", "city": "Tucson, AZ", "weight": 88},
    {"id": 3536799, "name": "BASIS Mesa", "city": "Mesa, AZ", "weight": 85},
    
    # KIPP Charter (real)
    {"id": 155846, "name": "KIPP Academy Charter School", "city": "Bronx, NY", "weight": 85},
    
    # Elite Prep Schools (real)
    {"id": 185742, "name": "Berkeley Preparatory School", "city": "Tampa, FL", "weight": 78},
    {"id": 168570, "name": "Georgetown Preparatory School", "city": "Rockville, MD", "weight": 80},
    {"id": 145364, "name": "Phillips Academy Andover", "city": "Andover, MA", "weight": 75},
    {"id": 148201, "name": "Phillips Exeter Academy", "city": "Exeter, NH", "weight": 75},
    
    # Top 50 US - Verified
    {"id": 202063, "name": "Signature School Inc", "city": "Evansville, IN", "weight": 95},
    {"id": 183857, "name": "School For Advanced Studies Homestead", "city": "Homestead, FL", "weight": 92},
    {"id": 3506727, "name": "Loveless Academic Magnet Program High School (LAMP)", "city": "Montgomery, AL", "weight": 90},
    {"id": 178685, "name": "Gwinnett School Of Mathematics, Science And Technology", "city": "Lawrenceville, GA", "weight": 88},
    {"id": 174195, "name": "North Carolina School of Science and Mathematics", "city": "Durham, NC", "weight": 90},
    
    # Public High Schools with real IDs
    {"id": 242400, "name": "Westlake High School", "city": "Austin, TX", "weight": 82},
    {"id": 269511, "name": "Bellevue High School", "city": "Bellevue, WA", "weight": 80},
    {"id": 270998, "name": "Lincoln High School", "city": "Tacoma, WA", "weight": 78},
    {"id": 268293, "name": "Lincoln High School", "city": "Portland, OR", "weight": 76},
    {"id": 257321, "name": "Lincoln High School", "city": "San Diego, CA", "weight": 75},
    
    # School districts sebagai alternatif
    {"id": 3706876, "name": "Harmony Science Academy", "city": "Dallas, TX", "weight": 80},
    {"id": 10148026, "name": "Fulton Science Academy", "city": "Alpharetta, GA", "weight": 85},
    {"id": 3704829, "name": "Bio-Med Science Academy STEM School", "city": "Rootstown, OH", "weight": 82},
]


def select_school():
    """Weighted random selection of K12 school"""
    weights = [s["weight"] for s in K12_SCHOOLS]
    total = sum(weights)
    r = random.uniform(0, total)
    cumulative = 0
    for school in K12_SCHOOLS:
        cumulative += school["weight"]
        if r <= cumulative:
            return {"id": school["id"], "idExtended": str(school["id"]), "name": school["name"], "type": "K12"}
    return {"id": K12_SCHOOLS[0]["id"], "idExtended": str(K12_SCHOOLS[0]["id"]), "name": K12_SCHOOLS[0]["name"], "type": "K12"}

# ============ NAME GENERATOR ============
FIRST_NAMES = [
    # Nama depan laki-laki populer Inggris
    "Oliver", "George", "Arthur", "Noah", "Leo", "Oscar", "Harry", "Jack",
    "Henry", "Charlie", "Freddie", "Theo", "Alfie", "Thomas", "Archie",
    "Joshua", "William", "Max", "Isaac", "Lucas", "Jacob", "Ethan",
    "Samuel", "Joseph", "Alexander", "Daniel", "Benjamin", "Matthew",
    "Luke", "Ryan", "Adam", "Harrison", "Harvey", "Louis", "Toby",
    "Reuben", "Nathan", "Gabriel", "Caleb", "Sebastian", "Edward",
    "Patrick", "Rory", "Connor", "Finley", "Jamie", "Kai", "Zachary",
    "Evan", "Aaron", "Callum", "Brandon", "Tyler", "Jayden", "Kian",
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
    "Thomas", "Christopher", "Charles", "Daniel", "Matthew", "Anthony", "Mark",
    "Donald", "Steven", "Andrew", "Paul", "Joshua", "Kenneth", "Kevin", "Brian",
    "George", "Timothy", "Ronald", "Edward", "Jason", "Jeffrey", "Ryan",
    "Jacob", "Nicholas", "Eric", "Jonathan", "Stephen", "Larry", "Justin", "Scott",
    "Brandon", "Benjamin", "Samuel", "Raymond", "Gregory", "Frank", "Alexander",
    # Nama depan perempuan populer Inggris
    "Olivia", "Amelia", "Isla", "Ava", "Emily", "Isabella", "Mia", "Poppy",
    "Ella", "Lily", "Sophia", "Grace", "Freya", "Chloe", "Evie", "Sophie",
    "Charlotte", "Daisy", "Alice", "Florence", "Scarlett", "Ruby", "Evelyn",
    "Harper", "Ellie", "Maisie", "Ivy", "Rosie", "Elsie", "Phoebe", "Luna",
    "Willow", "Matilda", "Holly", "Imogen", "Layla", "Esme", "Eliza", "Maya",
    "Thea", "Orla", "Robyn", "Lydia", "Erin", "Darcy", "Zara", "Lottie",
    "Niamh", "Cora", "Bethany", "Katie", "Molly", "Lucy", "Jessica", "Hannah",
    "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan",
    "Jessica", "Sarah", "Karen", "Lisa", "Nancy", "Betty", "Margaret", "Sandra",
    "Ashley", "Kimberly", "Emily", "Donna", "Michelle", "Dorothy", "Carol",
    "Amanda", "Melissa", "Deborah", "Stephanie", "Rebecca", "Sharon", "Laura",
    "Emma", "Olivia", "Ava", "Isabella", "Sophia", "Mia", "Charlotte", "Amelia",
    "Harper", "Evelyn", "Abigail", "Ella", "Scarlett", "Grace", "Victoria", "Riley"
]

LAST_NAMES = [
    # Nama belakang populer Inggris
    "Brown", "Taylor", "Wilson", "Evans", "Thomas", "Roberts", "Johnson",
    "Williams", "Jones", "Davies", "Robinson", "Wright", "Thompson", "Walker",
    "White", "Edwards", "Green", "Hall", "Wood", "Harris", "Lewis", "Martin",
    "Jackson", "Clarke", "Clark", "Turner", "Hill", "Moore", "Cooper",
    "King", "Lee", "Baker", "Harrison", "Morgan", "Allen", "James", "Scott",
    "Phillips", "Watson", "Davis", "Parker", "Price", "Bennett", "Young",
    "Griffiths", "Mitchell", "Kelly", "Cook", "Carter", "Richardson", "Bailey",
    "Collins", "Bell", "Shaw", "Murphy", "Miller", "Cox", "Richards", "Marshall",
    "Anderson", "Chapman", "Mason", "Webb", "Rogers", "Stevens", "Fisher",
    "Barnes", "Hughes", "Knight", "Harvey", "Lloyd", "Russell", "Graham",
    "Fletcher", "Murray", "Gibson", "Howard", "Dean", "Simpson", "Pearson",
    "Bradley", "Gardner", "Stone", "Berry", "Hunt", "Palmer", "Holmes",
    "Mills", "Payne", "West", "Grant", "Ellis", "Reynolds", "Hamilton",
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill",
    "Flores", "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell",
    "Mitchell", "Carter", "Roberts", "Turner", "Phillips", "Evans", "Parker", "Edwards",
    "Collins", "Stewart", "Morris", "Murphy", "Cook", "Rogers", "Morgan", "Peterson",
    "Cooper", "Reed", "Bailey", "Bell", "Gomez", "Kelly", "Howard", "Ward"
]


def generate_name() -> Tuple[str, str]:
    return random.choice(FIRST_NAMES), random.choice(LAST_NAMES)


def generate_email_data(first_name: str, last_name: str, use_temp_email=True, 
                       proxy_config=None, verification_session=None,
                       manual_email: str = None) -> Tuple[str, Any]:
    """
    Generate email dengan berbagai opsi.
    
    Args:
        manual_email: Jika diberikan, gunakan email ini (manual input)
    
    Returns: (email_address, email_service_or_None)
    """
    if manual_email:
        # Gunakan email manual
        print(f"   [EMAIL] Using manual email: {manual_email}")
        # Buat temp service untuk menangani jika perlu, tapi dengan manual email flag
        temp_service = TempEmailService(
            proxy_config=proxy_config,
            verification_session=verification_session,
            email_address=manual_email  # Set manual email
        )
        return manual_email, temp_service
    
    if use_temp_email:
        # Gunakan temporary email service dengan session
        temp_service = TempEmailService(
            proxy_config=proxy_config,
            verification_session=verification_session
        )
        email = temp_service.generate_email()
        return email, temp_service
    else:
        # Gunakan email biasa yang di-generate
        suffix = random.randint(100, 999)
        domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]
        domain = random.choice(domains)
        email = f"{first_name.lower()}.{last_name.lower()}{suffix}@{domain}"
        print(f"   [EMAIL] Generated regular email: {email}")
        return email, None


def generate_birth_date() -> str:
    """Generate birth date (25-55 years old for teacher)"""
    year = random.randint(1970, 2000)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year}-{month:02d}-{day:02d}"


def generate_fingerprint() -> str:
    chars = "0123456789abcdef"
    return "".join(random.choice(chars) for _ in range(32))


# ============ IMAGE GENERATOR ============
def generate_white_image() -> bytes:
    """Generate pure white image for bypass when stuck on emailLoop"""
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_teacher_badge(first_name: str, last_name: str, school_name: str) -> bytes:
    """Generate fake K12 teacher badge PNG"""
    width, height = 500, 350
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    try:
        title_font = ImageFont.truetype("arial.ttf", 22)
        text_font = ImageFont.truetype("arial.ttf", 16)
        small_font = ImageFont.truetype("arial.ttf", 12)
    except:
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    # Header bar
    draw.rectangle([(0, 0), (width, 50)], fill=(34, 139, 34))  # Forest green
    draw.text((width//2, 25), "STAFF IDENTIFICATION", fill=(255, 255, 255), 
              font=title_font, anchor="mm")
    
    # School name
    draw.text((width//2, 75), school_name, fill=(34, 139, 34), font=text_font, anchor="mm")
    
    # Photo placeholder
    draw.rectangle([(25, 100), (125, 220)], outline=(200, 200, 200), width=2)
    draw.text((75, 160), "PHOTO", fill=(200, 200, 200), font=text_font, anchor="mm")
    
    # Teacher info
    teacher_id = f"T{random.randint(10000, 99999)}"
    info_y = 110
    info_lines = [
        f"Name: {first_name} {last_name}",
        f"ID: {teacher_id}",
        f"Position: Teacher",
        f"Department: Education",
        f"Status: Active"
    ]
    
    for line in info_lines:
        draw.text((145, info_y), line, fill=(51, 51, 51), font=text_font)
        info_y += 22
    
    # Valid date
    current_year = int(time.strftime("%Y"))
    draw.text((145, info_y + 10), f"Valid: {current_year}-{current_year+1} School Year", 
              fill=(100, 100, 100), font=small_font)
    
    # Footer
    draw.rectangle([(0, height-35), (width, height)], fill=(34, 139, 34))
    draw.text((width//2, height-18), "Property of School District", 
              fill=(255, 255, 255), font=small_font, anchor="mm")
    
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


# ============ VERIFIER ============
class K12Verifier:
    """K12 Teacher Verification"""
    
    def __init__(self, verification_url: str, proxy: str = None, debug: bool = False, 
                 use_temp_email: bool = True, manual_email: str = None):
        self.debug_mode = debug
        self.verification_url = verification_url
        self.device_fingerprint = generate_fingerprint()
        self.use_temp_email = use_temp_email
        self.manual_email = manual_email  # Menyimpan email manual
        self.email_service = None
        
        # Parse verification ID
        self.verification_id = self._parse_verification_id(verification_url)
        
        # Setup proxy untuk requests dan email service
        self.proxy_config = self._setup_proxy_config(proxy)
        
        # Create HTTP client
        self.client = self._create_http_client(proxy)
        
        if debug:
            print(f"[DEBUG] Client initialized")
            print(f"[DEBUG] Verification URL: {verification_url}")
            print(f"[DEBUG] Parsed verification ID: {self.verification_id}")
            if proxy:
                print(f"[DEBUG] Proxy config: {self.proxy_config}")
            if manual_email:
                print(f"[DEBUG] Manual email: {manual_email}")
    
    def _setup_proxy_config(self, proxy_str: str):
        """Setup proxy configuration untuk requests library"""
        if not proxy_str:
            return None
        
        proxy_url = self._parse_proxy_url(proxy_str)
        if proxy_url:
            return {
                "http": proxy_url,
                "https": proxy_url
            }
        return None
    
    def _create_http_client(self, proxy_str: str):
        """Create httpx client dengan kompatibilitas maksimal"""
        import httpx
        
        if not proxy_str:
            return httpx.Client(timeout=30.0)
        
        proxy_url = self._parse_proxy_url(proxy_str)
        if not proxy_url:
            return httpx.Client(timeout=30.0)
        
        # Coba berbagai metode
        try:
            # Method 1: proxies sebagai string
            return httpx.Client(timeout=30.0, proxies=proxy_url)
        except Exception as e1:
            if self.debug_mode:
                print(f"[DEBUG] Proxy method 1 failed: {e1}")
            try:
                # Method 2: transport
                transport = httpx.HTTPTransport(proxy=httpx.Proxy(proxy_url))
                return httpx.Client(timeout=30.0, transport=transport)
            except Exception as e2:
                if self.debug_mode:
                    print(f"[DEBUG] Proxy method 2 failed: {e2}")
                # Method 3: fallback tanpa proxy
                print(f"[WARNING] Proxy setup failed, using direct connection")
                return httpx.Client(timeout=30.0)
    
    def _parse_proxy_url(self, proxy_str: str) -> str:
        """Parse proxy string menjadi URL"""
        if not proxy_str:
            return None
        
        # Jika sudah format URL, langsung pakai
        if proxy_str.startswith(('http://', 'https://')):
            return proxy_str
        
        # Format: user:pass@host:port atau host:port
        if ':' in proxy_str:
            return f"http://{proxy_str}"
        
        return None
    
    def __del__(self):
        if hasattr(self, "client"):
            self.client.close()
    
    def _parse_verification_id(self, url: str) -> Optional[str]:
        # Mencari verificationId dalam URL dengan berbagai pattern
        patterns = [
            r"verificationId=([a-f0-9]+)",  # Standard pattern
            r"verificationId%3D([a-f0-9]+)", # URL encoded
            r"verificationId%253D([a-f0-9]+)", # Double encoded
            r"/([a-f0-9]{20,})"  # Fallback: long hex string in path
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                if self.debug_mode:
                    print(f"[DEBUG] Found verificationId with pattern '{pattern}': {match.group(1)}")
                return match.group(1)
        
        # Coba ekstrak dari query parameters manual
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            if 'verificationId' in params:
                vid = params['verificationId'][0]
                if self.debug_mode:
                    print(f"[DEBUG] Found verificationId via parse_qs: {vid}")
                return vid
        except Exception as e:
            if self.debug_mode:
                print(f"[DEBUG] parse_qs failed: {e}")
        
        if self.debug_mode:
            print(f"[DEBUG] No verificationId found in URL")
        return None
    
    def _request(self, method: str, url: str, body: Dict = None) -> Tuple[Dict, int]:
        headers = {"Content-Type": "application/json"}
        try:
            if self.debug_mode:
                print(f"\n{'='*60}")
                print(f"[DEBUG REQUEST]")
                print(f"  Method: {method}")
                print(f"  URL: {url}")
                if body:
                    body_str = json.dumps(body, indent=2)
                    print(f"  Body ({len(body_str)} chars):")
                    # Tampilkan maksimal 1000 karakter untuk readability
                    if len(body_str) > 1000:
                        print(f"  {body_str[:1000]}...")
                    else:
                        print(f"  {body_str}")
                else:
                    print(f"  Body: None")
                print(f"{'-'*60}")
            
            response = self.client.request(method=method, url=url, json=body, headers=headers)
            
            if self.debug_mode:
                print(f"[DEBUG RESPONSE]")
                print(f"  Status: {response.status_code}")
                print(f"  Headers: {dict(response.headers)}")
                response_text = response.text
                print(f"  Response ({len(response_text)} chars):")
                if len(response_text) > 1000:
                    print(f"  {response_text[:1000]}...")
                else:
                    print(f"  {response_text}")
                print(f"{'='*60}")
            
            try:
                data = response.json()
            except:
                data = {"text": response.text}
            return data, response.status_code
        except Exception as e:
            if self.debug_mode:
                print(f"[DEBUG ERROR] Request failed: {e}")
            raise Exception(f"Request failed: {e}")
    
    def _upload_to_s3(self, upload_url: str, data: bytes, mime_type: str) -> bool:
        try:
            if self.debug_mode:
                print(f"[DEBUG] Uploading {len(data)} bytes to S3")
                print(f"       MIME Type: {mime_type}")
                print(f"       URL (first 100 chars): {upload_url[:100]}...")
            
            response = self.client.put(upload_url, content=data, 
                                       headers={"Content-Type": mime_type}, timeout=60.0)
            
            if self.debug_mode:
                print(f"[DEBUG] S3 upload status: {response.status_code}")
                if response.status_code >= 400:
                    print(f"[DEBUG] S3 upload error: {response.text[:200]}")
            
            return 200 <= response.status_code < 300
        except Exception as e:
            print(f"   [ERROR] Upload ke S3 gagal: {e}")
            return False
    
    def verify(self) -> Dict:
        if not self.verification_id:
            return {"success": False, "error": "URL verifikasi tidak valid - tidak menemukan verificationId"}
        
        if self.debug_mode:
            print(f"\n[DEBUG] ===== VERIFICATION START =====")
            print(f"[DEBUG] Verification ID: {self.verification_id}")
        
        try:
            first_name, last_name = generate_name()
            birth_date = generate_birth_date()
            school = select_school()
            
            # Generate email dengan opsi manual
            email, self.email_service = generate_email_data(
                first_name, last_name, 
                use_temp_email=self.use_temp_email,
                proxy_config=self.proxy_config,
                verification_session=self.client,  # PASS SESSION!
                manual_email=self.manual_email  # PASS MANUAL EMAIL
            )
            
            print(f"   Guru: {first_name} {last_name}")
            print(f"   Email: {email}")
            print(f"   Sekolah: {school['name']}")
            print(f"   Tanggal lahir: {birth_date}")
            
            if self.debug_mode:
                print(f"\n[DEBUG] Generated data:")
                print(f"  First Name: {first_name}")
                print(f"  Last Name: {last_name}")
                print(f"  Email: {email}")
                print(f"  Birth Date: {birth_date}")
                print(f"  School: {school['name']} (ID: {school['id']})")
                print(f"  School Type: {school['type']}")
            
            # Step 1: Generate teacher badge
            print("\n   -> Langkah 1/4: Membuat kartu identitas guru...")
            doc_data = generate_teacher_badge(first_name, last_name, school["name"])
            doc_size_kb = len(doc_data) / 1024
            print(f"      Ukuran dokumen: {doc_size_kb:.2f} KB")
            
            if self.debug_mode:
                print(f"[DEBUG] Generated badge: {len(doc_data)} bytes ({doc_size_kb:.2f} KB)")
            
            # Step 2: Submit teacher info
            print("   -> Langkah 2/4: Mengirim informasi guru...")
            step2_body = {
                "firstName": first_name,
                "lastName": last_name,
                "birthDate": birth_date,
                "email": email,
                "phoneNumber": "",
                "organization": {
                    "id": school["id"],
                    "idExtended": school["idExtended"],
                    "name": school["name"]
                },
                "deviceFingerprintHash": self.device_fingerprint,
                "locale": "en-US",
                "metadata": {
                    "marketConsentValue": False,
                    "submissionOptIn": "By submitting the personal information above, I acknowledge that my personal information is being collected under the privacy policy of the business from which I am seeking a discount"
                }
            }
            
            if self.debug_mode:
                print(f"\n[DEBUG] Step 2 - Submit Teacher Info")
                print(f"  Endpoint: /rest/v2/verification/{self.verification_id}/step/collectTeacherPersonalInfo")
            
            data, status = self._request(
                "POST",
                f"{SHEERID_BASE_URL}/rest/v2/verification/{self.verification_id}/step/collectTeacherPersonalInfo",
                step2_body
            )
            
            if status != 200:
                if self.debug_mode:
                    print(f"[DEBUG] Step 2 failed with status {status}")
                    print(f"[DEBUG] Full response: {data}")
                
                # Berikan error message yang lebih informatif
                error_msg = f"Langkah 2 gagal: Status {status}"
                if isinstance(data, dict):
                    if 'errorIds' in data:
                        error_msg += f" - Errors: {', '.join(data['errorIds'])}"
                    elif 'text' in data:
                        error_msg += f" - Response: {data['text'][:200]}"
                    elif 'message' in data:
                        error_msg += f" - Message: {data['message']}"
                
                return {"success": False, "error": error_msg}
            
            if self.debug_mode:
                print(f"[DEBUG] Step 2 successful - Status 200")
            
            if isinstance(data, dict) and data.get("currentStep") == "error":
                error_msg = ", ".join(data.get("errorIds", ["Unknown"]))
                return {"success": False, "error": f"Langkah 2 error: {error_msg}"}
            
            current_step = data.get("currentStep", "") if isinstance(data, dict) else ""
            print(f"      Langkah saat ini: {current_step}")
            
            if self.debug_mode and current_step:
                print(f"[DEBUG] Current step after submission: {current_step}")
                if isinstance(data, dict):
                    # Tampilkan data penting lainnya
                    important_keys = ['status', 'result', 'errors', 'warnings']
                    for key in important_keys:
                        if key in data:
                            print(f"[DEBUG] {key}: {data[key]}")
            
            # Check for auto-pass (K12 often doesn't need upload!)
            if current_step == "success":
                print("   BERHASIL! AUTO-PASS! Tidak perlu upload dokumen!")
                if self.debug_mode:
                    print(f"[DEBUG] AUTO-PASS achieved! Verification complete.")
                return {
                    "success": True,
                    "message": "Verifikasi disetujui otomatis! Tidak perlu dokumen.",
                    "teacher": f"{first_name} {last_name}",
                    "email": email,
                    "auto_pass": True
                }
            
            # Step 3: Skip SSO if needed
            if current_step in ["sso", "collectTeacherPersonalInfo"]:
                print("   -> Langkah 3/5: Melewati SSO...")
                if self.debug_mode:
                    print(f"[DEBUG] Skipping SSO step...")
                
                data, _ = self._request(
                    "DELETE",
                    f"{SHEERID_BASE_URL}/rest/v2/verification/{self.verification_id}/step/sso"
                )
                current_step = data.get("currentStep", "") if isinstance(data, dict) else ""
                
                if self.debug_mode:
                    print(f"[DEBUG] After SSO skip, current step: {current_step}")
                
                # Check again for auto-pass after SSO skip
                if current_step == "success":
                    print("   BERHASIL! AUTO-PASS setelah melewati SSO!")
                    return {
                        "success": True,
                        "message": "Verifikasi disetujui otomatis!",
                        "teacher": f"{first_name} {last_name}",
                        "email": email,
                        "auto_pass": True
                    }
            
            # Handle emailLoop step dengan auto-click
            if current_step == "emailLoop":
                print(f"\n   PERINGATAN: emailLoop terpicu untuk: {school['name']}")
                print(f"      Kombinasi sekolah/data ini memerlukan verifikasi email")
                
                # Jika email manual, beri instruksi
                if self.email_service and self.email_service.is_manual_email:
                    print(f"\n   [EMAIL MANUAL] PERHATIAN!")
                    print(f"   Email: {email}")
                    print(f"   Link verifikasi akan dikirim ke email Anda")
                    print(f"   Silakan cek email dan klik link verifikasi")
                    print(f"   Setelah itu, dapatkan link baru dari ChatGPT")
                    print(f"   dan jalankan script lagi dengan link baru")
                    
                    return {
                        "success": False,
                        "email_loop": True,
                        "manual_email": True,  # Flag khusus untuk email manual
                        "school": school["name"],
                        "teacher": f"{first_name} {last_name}",
                        "email": email,
                        "error": "emailLoop - verifikasi email manual diperlukan"
                    }
                
                # Untuk email temporary, coba auto-click
                print(f"   [EMAIL] Menunggu email verifikasi (10 detik)...")
                time.sleep(10)
                
                # Coba dapatkan dan klik link verifikasi dari email
                verification_result = None
                if self.email_service:
                    print(f"   [EMAIL] Mencoba mendapatkan dan OTOMATIS klik link verifikasi...")
                    verification_result = self.email_service.check_for_verification_link(
                        max_checks=10,  # Cek 10x
                        delay=5         # Setiap 5 detik
                    )
                
                if verification_result == "AUTO_CLICKED":
                    print(f"\n   VERIFIKASI EMAIL BERHASIL DIAUTOMASI!")
                    print(f"   Link verifikasi telah diklik otomatis")
                    print(f"   Tunggu beberapa saat untuk proses lanjutan...")
                    
                    # Tunggu dan coba lanjutkan verifikasi
                    time.sleep(5)
                    
                    # Coba lanjutkan proses
                    return {
                        "success": True,
                        "message": "Verifikasi email berhasil! Proses dilanjutkan...",
                        "teacher": f"{first_name} {last_name}",
                        "email": email,
                        "auto_clicked": True
                    }
                elif verification_result:
                    print(f"\n   LINK VERIFIKASI DITEMUKAN (manual):")
                    print(f"   {verification_result}")
                    
                    return {
                        "success": False,
                        "email_loop": True,
                        "school": school["name"],
                        "teacher": f"{first_name} {last_name}",
                        "email": email,
                        "verification_link": verification_result,
                        "error": "emailLoop - klik link manual"
                    }
                else:
                    return {
                        "success": False,
                        "email_loop": True,
                        "school": school["name"],
                        "teacher": f"{first_name} {last_name}",
                        "email": email,
                        "error": "emailLoop - tidak ada link ditemukan"
                    }
            
            # Step 4: Upload document
            print("   -> Langkah 4/4: Mengupload kartu identitas guru...")
            step4_body = {
                "files": [{
                    "fileName": "teacher_badge.png",
                    "mimeType": "image/png",
                    "fileSize": len(doc_data)
                }]
            }
            
            if self.debug_mode:
                print(f"\n[DEBUG] Step 4 - Initiate Document Upload")
                print(f"  Endpoint: /rest/v2/verification/{self.verification_id}/step/docUpload")
            
            data, status = self._request(
                "POST",
                f"{SHEERID_BASE_URL}/rest/v2/verification/{self.verification_id}/step/docUpload",
                step4_body
            )
            
            if status != 200 or not isinstance(data, dict) or not data.get("documents"):
                print(f"   [ERROR] Inisialisasi upload gagal. Status: {status}")
                if self.debug_mode:
                    print(f"[DEBUG] Upload init failed")
                    print(f"[DEBUG] Status: {status}")
                    print(f"[DEBUG] Response: {json.dumps(data, indent=2)}")
                return {"success": False, "error": "Gagal mendapatkan URL upload"}
            
            upload_url = data["documents"][0].get("uploadUrl")
            if not upload_url:
                if self.debug_mode:
                    print(f"[DEBUG] No upload URL in response")
                return {"success": False, "error": "Tidak ada URL upload yang dikembalikan"}
            
            if self.debug_mode:
                print(f"[DEBUG] Got upload URL: {upload_url[:100]}...")
            
            if not self._upload_to_s3(upload_url, doc_data, "image/png"):
                return {"success": False, "error": "Upload ke S3 gagal"}
            
            print("   [OK] Dokumen diupload!")
            
            # Step 5: Complete document upload
            print("   -> Langkah 5/5: Menyelesaikan upload...")
            if self.debug_mode:
                print(f"[DEBUG] Step 5 - Complete Document Upload")
            
            data, _ = self._request(
                "POST",
                f"{SHEERID_BASE_URL}/rest/v2/verification/{self.verification_id}/step/completeDocUpload"
            )
            
            final_step = data.get('currentStep', 'pending') if isinstance(data, dict) else 'pending'
            print(f"      Upload selesai: {final_step}")
            
            if self.debug_mode:
                print(f"[DEBUG] Final step after upload: {final_step}")
                if isinstance(data, dict) and 'status' in data:
                    print(f"[DEBUG] Verification status: {data['status']}")
                print(f"[DEBUG] ===== VERIFICATION COMPLETE =====")
            
            return {
                "success": True,
                "message": "Verifikasi dikirim! Tunggu review.",
                "teacher": f"{first_name} {last_name}",
                "email": email,
                "auto_pass": False
            }
            
        except Exception as e:
            if self.debug_mode:
                print(f"[DEBUG] Exception in verify(): {type(e).__name__}: {str(e)}")
                import traceback
                traceback.print_exc()
            return {"success": False, "error": str(e)}


def main():
    print()
    print("=" * 55)
    print("  Alat Verifikasi Guru K12")
    print("  Verifikasi Guru K12 SheerID (High School)")
    print("=" * 55)
    print()
    
    import argparse
    parser = argparse.ArgumentParser(description="Alat Verifikasi Guru K12")
    parser.add_argument("url", nargs="?", help="URL Verifikasi")
    parser.add_argument("--proxy", help="Proxy (format: IP:Port atau user:pass@IP:Port)")
    parser.add_argument("--debug", action="store_true", help="Mode debug (tampilkan detail request/response)")
    parser.add_argument("--no-temp-email", action="store_true", help="Gunakan email biasa, bukan temporary email")
    parser.add_argument("--email", help="Gunakan email manual (contoh: user@example.com)")
    parser.add_argument("--ask-email", action="store_true", help="Tanya email manual saat runtime")
    args = parser.parse_args()

    # Get URL from args or input
    if args.url:
        url = args.url
    else:
        url = input("Masukkan URL verifikasi: ").strip()
    
    if not url:
        print("[ERROR] URL tidak boleh kosong")
        return
    
    if "sheerid.com" not in url:
        print("[WARNING] URL mungkin tidak valid. Harus mengandung 'sheerid.com'")
        user_confirm = input("Lanjutkan anyway? (y/n): ").strip().lower()
        if user_confirm != 'y':
            print("Dibatalkan")
            return
    
    # Get email manual jika diperlukan
    manual_email = None
    if args.email:
        manual_email = args.email.strip()
    elif args.ask_email:
        manual_email = input("Masukkan email manual: ").strip()
        if not manual_email:
            print("[INFO] Tidak ada email manual diberikan, akan menggunakan opsi default")
    
    print(f"\n[INFO] Memproses URL...")
    if args.debug:
        print("[DEBUG] Mode debug aktif")
    
    use_temp_email = not args.no_temp_email
    if manual_email:
        print(f"[INFO] Menggunakan email manual: {manual_email}")
        use_temp_email = False  # Override, gunakan manual email
    elif use_temp_email:
        print("[INFO] Menggunakan temporary email service (otomatis klik link)")
    else:
        print("[INFO] Menggunakan email biasa")
    
    verifier = K12Verifier(
        url, 
        proxy=args.proxy, 
        debug=args.debug,
        use_temp_email=use_temp_email,
        manual_email=manual_email
    )
    result = verifier.verify()
    
    print()
    if result.get("success"):
        print("-" * 55)
        print("  [BERHASIL] Verifikasi dikirim!")
        print(f"  Guru: {result.get('teacher')}")
        print(f"  Email: {result.get('email')}")
        if result.get("auto_pass"):
            print("  Status: AUTO-PASS (langsung disetujui)")
        elif result.get("auto_clicked"):
            print("  Status: Verifikasi email berhasil (otomatis)")
        else:
            print("  Status: Menunggu review dokumen")
        print("-" * 55)
    
    elif result.get("email_loop"):
        print("-" * 55)
        print("  PERINGATAN: VERIFIKASI EMAIL DIPERLUKAN")
        print("-" * 55)
        print(f"  Sekolah: {result.get('school')}")
        print(f"  Guru: {result.get('teacher')}")
        print(f"  Email: {result.get('email')}")
        
        # Tampilkan pesan khusus untuk email manual
        if result.get("manual_email"):
            print(f"\n  [EMAIL MANUAL INSTRUCTION]")
            print(f"  1. Buka email: {result.get('email')}")
            print(f"  2. Cari email dari SheerID")
            print(f"  3. Klik link verifikasi di email")
            print(f"  4. Tunggu 1-2 menit")
            print(f"  5. Dapatkan LINK VERIFIKASI BARU dari ChatGPT K12")
            print(f"  6. Jalankan alat ini lagi dengan link baru")
        elif result.get("verification_link"):
            print(f"\n  LINK VERIFIKASI DITEMUKAN:")
            print(f"  {result.get('verification_link')}")
            print(f"\n  INSTRUKSI MANUAL:")
            print(f"  1. Buka link di atas di browser")
            print(f"  2. Klik tombol 'Verify Email' atau 'Confirm Email'")
            print(f"  3. Setelah verifikasi, dapatkan link baru dari ChatGPT")
            print(f"  4. Jalankan script lagi dengan link baru")
        else:
            print(f"\n  SOLUSI:")
            print(f"  1. Cek email: {result.get('email')}")
            print(f"  2. Klik link verifikasi dari SheerID")
            print(f"  3. Tunggu 1-2 menit")
            print(f"  4. Dapatkan LINK VERIFIKASI BARU dari ChatGPT K12")
            print(f"  5. Jalankan alat ini lagi dengan link baru")
        
        print("-" * 55)
    
    else:
        print(f"  [GAGAL] {result.get('error')}")

if __name__ == "__main__":
    main()