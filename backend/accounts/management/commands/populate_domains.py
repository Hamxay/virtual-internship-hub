from django.core.management.base import BaseCommand
from accounts.models import Domain

class Command(BaseCommand):
    help = 'Populate domains table with initial data'

    def handle(self, *args, **options):
        domains_data = [
            # DigiSkills Courses
            {'name': 'Freelancing', 'code': 'FREELANCING', 'description': 'Freelance business and entrepreneurship'},
            {'name': 'Digital Marketing', 'code': 'DIGITAL_MARKETING', 'description': 'Digital marketing strategies and online promotion'},
            {'name': 'E-Commerce Management', 'code': 'E_COMMERCE_MANAGEMENT', 'description': 'E-commerce platform management and online business'},
            {'name': 'Graphic Design', 'code': 'GRAPHIC_DESIGN', 'description': 'Graphic design and visual communication'},
            {'name': 'SEO', 'code': 'SEO', 'description': 'Search Engine Optimization and website visibility'},
            {'name': 'WordPress', 'code': 'WORDPRESS', 'description': 'WordPress website development and management'},
            {'name': 'Virtual Assistant', 'code': 'VIRTUAL_ASSISTANT', 'description': 'Virtual assistance and administrative support'},
            {'name': 'Creative Writing', 'code': 'CREATIVE_WRITING', 'description': 'Creative writing and content creation'},
            {'name': 'Data Analytics', 'code': 'DATA_ANALYTICS', 'description': 'Data analysis and business intelligence'},
            {'name': 'Video Editing', 'code': 'VIDEO_EDITING', 'description': 'Video editing and post-production'},
            {'name': 'AutoCAD', 'code': 'AUTOCAD', 'description': 'AutoCAD design and drafting'},
            {'name': 'Affiliate Marketing', 'code': 'AFFILIATE_MARKETING', 'description': 'Affiliate marketing and commission-based sales'},
            {'name': 'Communication & Soft Skills', 'code': 'COMMUNICATION_SOFT_SKILLS', 'description': 'Communication skills and professional development'},
            {'name': 'QuickBooks', 'code': 'QUICKBOOKS', 'description': 'QuickBooks accounting and bookkeeping'},
            {'name': 'Startup Strategies', 'code': 'STARTUP_STRATEGIES', 'description': 'Startup planning and business strategies'},
            {'name': 'Digital Literacy', 'code': 'DIGITAL_LITERACY', 'description': 'Digital skills and computer literacy'},
            
            # Coding and Programming Domains
            {'name': 'Web Development', 'code': 'WEB_DEVELOPMENT', 'description': 'Full-stack web development'},
            {'name': 'Frontend Development', 'code': 'FRONTEND_DEVELOPMENT', 'description': 'Frontend web development (HTML, CSS, JavaScript)'},
            {'name': 'Backend Development', 'code': 'BACKEND_DEVELOPMENT', 'description': 'Backend development and server-side programming'},
            {'name': 'Mobile App Development', 'code': 'MOBILE_APP_DEVELOPMENT', 'description': 'Mobile application development (iOS/Android)'},
            {'name': 'Python Programming', 'code': 'PYTHON_PROGRAMMING', 'description': 'Python programming and development'},
            {'name': 'JavaScript Development', 'code': 'JAVASCRIPT_DEVELOPMENT', 'description': 'JavaScript and modern web development'},
            {'name': 'Java Programming', 'code': 'JAVA_PROGRAMMING', 'description': 'Java programming and enterprise development'},
            {'name': 'C# Programming', 'code': 'C_SHARP_PROGRAMMING', 'description': 'C# programming and .NET development'},
            {'name': 'PHP Development', 'code': 'PHP_DEVELOPMENT', 'description': 'PHP web development'},
            {'name': 'React Development', 'code': 'REACT_DEVELOPMENT', 'description': 'React.js frontend development'},
            {'name': 'Node.js Development', 'code': 'NODEJS_DEVELOPMENT', 'description': 'Node.js backend development'},
            {'name': 'Database Management', 'code': 'DATABASE_MANAGEMENT', 'description': 'Database design and management (SQL, NoSQL)'},
            {'name': 'Software Engineering', 'code': 'SOFTWARE_ENGINEERING', 'description': 'Software engineering and system design'},
            {'name': 'Cloud Computing', 'code': 'CLOUD_COMPUTING', 'description': 'Cloud platforms (AWS, Azure, GCP)'},
            {'name': 'DevOps', 'code': 'DEVOPS', 'description': 'DevOps and CI/CD practices'},
            {'name': 'Machine Learning / AI', 'code': 'MACHINE_LEARNING_AI', 'description': 'Machine learning and artificial intelligence'},
            {'name': 'Cybersecurity', 'code': 'CYBERSECURITY', 'description': 'Cybersecurity and information security'},
            {'name': 'Game Development', 'code': 'GAME_DEVELOPMENT', 'description': 'Game development and design'},
            {'name': 'Blockchain Development', 'code': 'BLOCKCHAIN_DEVELOPMENT', 'description': 'Blockchain and cryptocurrency development'},
            # Design
            {'name': 'UI/UX Design', 'code': 'UI_UX_DESIGN', 'description': 'User interface and user experience design'},
        ]
        
        created_count = 0
        for domain_data in domains_data:
            domain, created = Domain.objects.get_or_create(
                code=domain_data['code'],
                defaults={
                    'name': domain_data['name'],
                    'description': domain_data['description']
                }
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created domain: {domain.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Domain already exists: {domain.name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'\nSuccessfully populated {created_count} domains')
        )

