import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')  
django.setup()

from extractor.models import Receipt, CustomUser
from faker import Faker
from decimal import Decimal
import random

fake = Faker()

def create_fake_receipts(num_receipts=20):
    users = CustomUser.objects.all()
    if not users.exists():
        print("No users found. Create users first.")
        return

    for _ in range(num_receipts):
        Receipt.objects.create(
            file=None,
            date=fake.date_between(start_date='-1y', end_date='today'),
            vendor=fake.company(),
            total_amount=Decimal(random.randrange(10, 5001)) / 100,  # Random amount between 0.10 and 50.00
            user=random.choice(users)
        )
    print(f"{num_receipts} fake receipts created successfully!")

if __name__ == '__main__':
    create_fake_receipts()
