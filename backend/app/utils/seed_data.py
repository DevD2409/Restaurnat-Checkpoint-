import json
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine, Base
from app.core.security import get_password_hash, generate_table_qr_token
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.models.table import Table, TableSession, TableStatus
from app.models.menu import MenuCategory, MenuItem, MenuCustomizationGroup, MenuCustomizationOption
from app.models.order import Order, OrderItem, OrderStatusHistory, OrderStatus, OrderPriority, PaymentStatus
from app.models.service_request import ServiceRequest, ServiceRequestType, ServiceRequestStatus
from app.models.reservation import Reservation, ReservationStatus
from app.models.billing import Bill, BillSplit, Payment, BillStatus, SplitType, PaymentMethod, PaymentRecordStatus

def seed_database():
    # Create all tables in database
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # Check if restaurant already exists
        existing_restaurant = db.query(Restaurant).first()
        if existing_restaurant:
            print("Database already seeded. Skipping initial seed.")
            return

        print("Seeding database with realistic restaurant data...")

        # 1. Restaurant Profile
        restaurant = Restaurant(
            name="The Royal Saffron - Smart Bistro & Lounge",
            tagline="Contemporary Indian Cuisine & Artisanal Mixology",
            address="Plot 42, Galleria Boulevard, Cyber Hub, Gurugram, India",
            phone="+91 98765 43210",
            email="concierge@royalsaffron.com",
            gst_number="07AABCR9603R1ZM",
            tax_percentage=5.0,  # 5% GST
            service_charge_percentage=5.0,  # 5% Service Charge
            currency="INR",
            currency_symbol="₹",
            wifi_ssid="RoyalSaffron-Guest-HighSpeed",
            wifi_password="SaffronDining2026",
            wifi_instructions="Connect to 'RoyalSaffron-Guest-HighSpeed'. Open your browser to access the captive high-speed internet portal. Complimentary for guests.",
            opening_time="11:30 AM",
            closing_time="11:30 PM",
            is_active=True
        )
        db.add(restaurant)
        db.commit()
        db.refresh(restaurant)

        # 2. Staff & Admin Users
        users = [
            User(
                restaurant_id=restaurant.id,
                email="admin@royalsaffron.com",
                username="admin",
                hashed_password=get_password_hash("admin123"),
                full_name="Arjun Verma",
                role=UserRole.ADMIN,
                phone_number="+91 98111 00001",
                is_active=True
            ),
            User(
                restaurant_id=restaurant.id,
                email="manager@royalsaffron.com",
                username="manager",
                hashed_password=get_password_hash("manager123"),
                full_name="Priya Sharma",
                role=UserRole.MANAGER,
                phone_number="+91 98111 00002",
                is_active=True
            ),
            User(
                restaurant_id=restaurant.id,
                email="waiter@royalsaffron.com",
                username="waiter",
                hashed_password=get_password_hash("waiter123"),
                full_name="Rahul Singh",
                role=UserRole.WAITER,
                phone_number="+91 98111 00003",
                is_active=True
            ),
            User(
                restaurant_id=restaurant.id,
                email="chef@royalsaffron.com",
                username="chef",
                hashed_password=get_password_hash("chef123"),
                full_name="Chef Kabir Sen",
                role=UserRole.KITCHEN,
                phone_number="+91 98111 00004",
                is_active=True
            ),
            User(
                restaurant_id=restaurant.id,
                email="cashier@royalsaffron.com",
                username="cashier",
                hashed_password=get_password_hash("cashier123"),
                full_name="Ananya Roy",
                role=UserRole.CASHIER,
                phone_number="+91 98111 00005",
                is_active=True
            ),
        ]
        db.add_all(users)
        db.commit()

        # 3. Tables
        table_configs = [
            {"num": "T-01", "cap": 2, "sec": "Terrace Garden", "x": 120, "y": 80, "status": TableStatus.OCCUPIED},
            {"num": "T-02", "cap": 4, "sec": "Main Dining", "x": 300, "y": 80, "status": TableStatus.AVAILABLE},
            {"num": "T-03", "cap": 4, "sec": "Main Dining", "x": 480, "y": 80, "status": TableStatus.ORDER_PENDING},
            {"num": "T-04", "cap": 6, "sec": "Main Dining", "x": 120, "y": 240, "status": TableStatus.BILL_REQUESTED},
            {"num": "T-05", "cap": 2, "sec": "Window Booth", "x": 300, "y": 240, "status": TableStatus.AVAILABLE},
            {"num": "T-06", "cap": 8, "sec": "VIP Lounge", "x": 480, "y": 240, "status": TableStatus.RESERVED},
            {"num": "T-07", "cap": 4, "sec": "Terrace Garden", "x": 120, "y": 400, "status": TableStatus.CLEANING},
            {"num": "T-08", "cap": 2, "sec": "Window Booth", "x": 300, "y": 400, "status": TableStatus.AVAILABLE},
            {"num": "T-09", "cap": 6, "sec": "Main Dining", "x": 480, "y": 400, "status": TableStatus.AVAILABLE},
            {"num": "T-10", "cap": 4, "sec": "VIP Lounge", "x": 660, "y": 240, "status": TableStatus.AVAILABLE},
        ]

        created_tables = []
        for idx, tc in enumerate(table_configs, start=1):
            qr_tok = generate_table_qr_token(restaurant.id, idx, tc["num"])
            tbl = Table(
                restaurant_id=restaurant.id,
                table_number=tc["num"],
                capacity=tc["cap"],
                section=tc["sec"],
                status=tc["status"],
                qr_token=qr_tok,
                pos_x=tc["x"],
                pos_y=tc["y"],
                is_active=True
            )
            created_tables.append(tbl)

        db.add_all(created_tables)
        db.commit()

        # 4. Menu Categories
        categories_data = [
            {"name": "Starters & Appetizers", "desc": "Small plates, tandoori grills and artisanal crisps", "icon": "Flame", "order": 1},
            {"name": "Main Course", "desc": "Slow-cooked curries, regional gravies and international specialties", "icon": "Soup", "order": 2},
            {"name": "Breads & Rice", "desc": "Clay oven artisanal naans and aromatic dum biryanis", "icon": "Wheat", "order": 3},
            {"name": "Artisanal Beverages", "desc": "Signature mocktails, fresh press juices and cold brews", "icon": "Coffee", "order": 4},
            {"name": "Desserts & Delights", "desc": "Contemporary Indo-Western desserts and confectionery", "icon": "IceCream", "order": 5},
        ]

        created_categories = []
        for cat in categories_data:
            c = MenuCategory(
                restaurant_id=restaurant.id,
                name=cat["name"],
                description=cat["desc"],
                icon=cat["icon"],
                display_order=cat["order"]
            )
            created_categories.append(c)

        db.add_all(created_categories)
        db.commit()

        # 5. Menu Items with Customization Groups
        items_data = [
            # Starters
            {
                "cat_idx": 0,
                "name": "Truffle Paneer Tikka",
                "desc": "Cottage cheese marinated in Kashmiri spices infused with black truffle oil and char-grilled in tandoor.",
                "price": 380.0,
                "is_veg": True,
                "is_bestseller": True,
                "prep_time": 15,
                "calories": 420,
                "tags": "Gluten-Free,Vegetarian,Chef Special",
                "spice": "Medium",
                "img": "https://images.unsplash.com/photo-1599488615731-7e5c2823ff28?w=600&auto=format&fit=crop&q=80",
                "customizations": [
                    {
                        "group_name": "Spice Level",
                        "is_required": True,
                        "min_select": 1,
                        "max_select": 1,
                        "options": [
                            {"name": "Mild", "price": 0.0, "is_default": False},
                            {"name": "Medium Spicy", "price": 0.0, "is_default": True},
                            {"name": "Extra Spicy", "price": 0.0, "is_default": False},
                        ]
                    },
                    {
                        "group_name": "Choice of Chutney",
                        "is_required": False,
                        "min_select": 0,
                        "max_select": 2,
                        "options": [
                            {"name": "Mint Coriander Dip", "price": 0.0, "is_default": True},
                            {"name": "Smoked Garlic Mayo", "price": 30.0, "is_default": False},
                            {"name": "Sweet Tamarind Glaze", "price": 20.0, "is_default": False},
                        ]
                    }
                ]
            },
            {
                "cat_idx": 0,
                "name": "Smoked Chicken Malai Seekh",
                "desc": "Tender minced chicken blended with cream, green cardamom, roasted cumin and melted cheese skewers.",
                "price": 440.0,
                "is_veg": False,
                "is_bestseller": True,
                "prep_time": 18,
                "calories": 490,
                "tags": "High-Protein,Chef Special",
                "spice": "Mild",
                "img": "https://images.unsplash.com/photo-1544025162-d76694265947?w=600&auto=format&fit=crop&q=80",
                "customizations": [
                    {
                        "group_name": "Add-ons",
                        "is_required": False,
                        "min_select": 0,
                        "max_select": 2,
                        "options": [
                            {"name": "Extra Melted Cheese Layer", "price": 50.0, "is_default": False},
                            {"name": "Romali Roti Wrap", "price": 40.0, "is_default": False},
                        ]
                    }
                ]
            },
            {
                "cat_idx": 0,
                "name": "Crispy Lotus Stem Honey Chilli",
                "desc": "Thinly sliced lotus root tossed in sesame chilli oil, scallions and organic wild honey.",
                "price": 340.0,
                "is_veg": True,
                "is_bestseller": False,
                "prep_time": 12,
                "calories": 310,
                "tags": "Vegan,Crunchy",
                "spice": "Medium",
                "img": "https://images.unsplash.com/photo-1540420773420-3366772f4999?w=600&auto=format&fit=crop&q=80",
                "customizations": []
            },
            {
                "cat_idx": 0,
                "name": "Coastal Prawn Koliwada",
                "desc": "Jumbo tiger prawns marinated with coastal spices, carom seeds and crisp fried with curry leaves.",
                "price": 560.0,
                "is_veg": False,
                "is_bestseller": True,
                "prep_time": 15,
                "calories": 380,
                "tags": "Seafood,Crispy",
                "spice": "Hot",
                "img": "https://images.unsplash.com/photo-1559847844-5315695dadae?w=600&auto=format&fit=crop&q=80",
                "customizations": []
            },

            # Main Course
            {
                "cat_idx": 1,
                "name": "Royal Butter Chicken 1947",
                "desc": "Succulent tandoor-roasted chicken simmered in a velvety tomato, cashew and churned butter gravy.",
                "price": 520.0,
                "is_veg": False,
                "is_bestseller": True,
                "prep_time": 20,
                "calories": 620,
                "tags": "Signature,Nut-Rich",
                "spice": "Mild",
                "img": "https://images.unsplash.com/photo-1588166524941-3bf61a9c41db?w=600&auto=format&fit=crop&q=80",
                "customizations": [
                    {
                        "group_name": "Portion & Meat Choice",
                        "is_required": True,
                        "min_select": 1,
                        "max_select": 1,
                        "options": [
                            {"name": "Boneless Chicken", "price": 0.0, "is_default": True},
                            {"name": "Traditional Bone-in", "price": 0.0, "is_default": False},
                        ]
                    },
                    {
                        "group_name": "Gravy Style",
                        "is_required": False,
                        "min_select": 0,
                        "max_select": 1,
                        "options": [
                            {"name": "Classic Sweet & Creamy", "price": 0.0, "is_default": True},
                            {"name": "Spicier Delhi Style", "price": 0.0, "is_default": False},
                        ]
                    }
                ]
            },
            {
                "cat_idx": 1,
                "name": "Dal Saffron Handi (Slow Cooked)",
                "desc": "Black lentils simmered overnight for 24 hours on slow charcoal embers with homemade white butter.",
                "price": 390.0,
                "is_veg": True,
                "is_bestseller": True,
                "prep_time": 10,
                "calories": 480,
                "tags": "Signature,Slow-Cooked",
                "spice": "Mild",
                "img": "https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=600&auto=format&fit=crop&q=80",
                "customizations": [
                    {
                        "group_name": "Garnish",
                        "is_required": False,
                        "min_select": 0,
                        "max_select": 1,
                        "options": [
                            {"name": "Extra White Makhan", "price": 40.0, "is_default": False},
                            {"name": "Fried Garlic & Cumin Tadka", "price": 30.0, "is_default": True},
                        ]
                    }
                ]
            },
            {
                "cat_idx": 1,
                "name": "Paneer Lababdar Royal",
                "desc": "Soft cottage cheese chunks cooked in rich onion, tomato and melon seed gravy finished with kasuri methi.",
                "price": 460.0,
                "is_veg": True,
                "is_bestseller": False,
                "prep_time": 15,
                "calories": 520,
                "tags": "Vegetarian,Creamy",
                "spice": "Medium",
                "img": "https://images.unsplash.com/photo-1565557623262-b51c2513a641?w=600&auto=format&fit=crop&q=80",
                "customizations": []
            },
            {
                "cat_idx": 1,
                "name": "Kashmiri Mutton Rogan Josh",
                "desc": "Prime mutton cuts braised with Persian saffron, Kashmiri dried red chillies and aromatic alkanet root.",
                "price": 640.0,
                "is_veg": False,
                "is_bestseller": True,
                "prep_time": 25,
                "calories": 680,
                "tags": "Heritage,Spicy",
                "spice": "Hot",
                "img": "https://images.unsplash.com/photo-1545247181-516773ca838b?w=600&auto=format&fit=crop&q=80",
                "customizations": []
            },

            # Breads & Rice
            {
                "cat_idx": 2,
                "name": "Awadhi Dum Gosht Biryani",
                "desc": "Fragrant aged basmati rice layered with tender mutton marinated in Awadhi spices, sealed in clay pot.",
                "price": 560.0,
                "is_veg": False,
                "is_bestseller": True,
                "prep_time": 20,
                "calories": 710,
                "tags": "Dum Pukht,Royal Special",
                "spice": "Medium",
                "img": "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=600&auto=format&fit=crop&q=80",
                "customizations": [
                    {
                        "group_name": "Accompaniment",
                        "is_required": False,
                        "min_select": 0,
                        "max_select": 1,
                        "options": [
                            {"name": "Burani Garlic Raita", "price": 0.0, "is_default": True},
                            {"name": "Pineapple Mint Raita", "price": 30.0, "is_default": False},
                            {"name": "Mirchi Ka Salan", "price": 40.0, "is_default": False},
                        ]
                    }
                ]
            },
            {
                "cat_idx": 2,
                "name": "Subz Dum Biryani",
                "desc": "Seasonal garden vegetables and cottage cheese simmered with saffron infused rice, caramelized onions.",
                "price": 420.0,
                "is_veg": True,
                "is_bestseller": False,
                "prep_time": 18,
                "calories": 540,
                "tags": "Vegetarian,Aromatic",
                "spice": "Medium",
                "img": "https://images.unsplash.com/photo-1642821373181-696a54913e93?w=600&auto=format&fit=crop&q=80",
                "customizations": []
            },
            {
                "cat_idx": 2,
                "name": "Garlic Truffle Butter Naan",
                "desc": "Soft leavened refined flour flatbread baked in clay oven, brushed with roasted garlic butter & truffle essence.",
                "price": 110.0,
                "is_veg": True,
                "is_bestseller": True,
                "prep_time": 8,
                "calories": 240,
                "tags": "Tandoor,Vegetarian",
                "spice": "Mild",
                "img": "https://images.unsplash.com/photo-1626074353765-517a681e40be?w=600&auto=format&fit=crop&q=80",
                "customizations": []
            },

            # Beverages
            {
                "cat_idx": 3,
                "name": "Saffron Badam Thandai Cooler",
                "desc": "Chilled almond milk infused with royal Kashmiri saffron, green cardamom, fennel and crushed pistachios.",
                "price": 240.0,
                "is_veg": True,
                "is_bestseller": True,
                "prep_time": 5,
                "calories": 210,
                "tags": "Chilled,Traditional",
                "spice": "Mild",
                "img": "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?w=600&auto=format&fit=crop&q=80",
                "customizations": []
            },
            {
                "cat_idx": 3,
                "name": "Smoked Charcoal Lemonade",
                "desc": "Fresh lime juice infused with activated charcoal, roasted cumin, sparkling soda and mint sprig.",
                "price": 190.0,
                "is_veg": True,
                "is_bestseller": False,
                "prep_time": 5,
                "calories": 95,
                "tags": "Refreshing,Detox",
                "spice": "Mild",
                "img": "https://images.unsplash.com/photo-1517256064527-09c73fc73e38?w=600&auto=format&fit=crop&q=80",
                "customizations": []
            },

            # Desserts
            {
                "cat_idx": 4,
                "name": "Gulab Jamun Cheesecake Fusion",
                "desc": "Baked New York cheesecake crust embedded with warm saffron gulab jamun, rose petal coulis and gold leaf.",
                "price": 290.0,
                "is_veg": True,
                "is_bestseller": True,
                "prep_time": 5,
                "calories": 390,
                "tags": "Fusion,Dessert",
                "spice": "Mild",
                "img": "https://images.unsplash.com/photo-1533134242443-d4fd215305ad?w=600&auto=format&fit=crop&q=80",
                "customizations": []
            },
            {
                "cat_idx": 4,
                "name": "Belgian Dark Chocolate Fondant",
                "desc": "Warm 70% Belgian chocolate molten cake served with artisanal Madagascar vanilla bean gelato.",
                "price": 340.0,
                "is_veg": True,
                "is_bestseller": False,
                "prep_time": 10,
                "calories": 460,
                "tags": "Chocolate,Decadent",
                "spice": "Mild",
                "img": "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?w=600&auto=format&fit=crop&q=80",
                "customizations": []
            }
        ]

        saved_items = []
        for item_info in items_data:
            cat = created_categories[item_info["cat_idx"]]
            menu_item = MenuItem(
                category_id=cat.id,
                name=item_info["name"],
                description=item_info["desc"],
                price=item_info["price"],
                is_veg=item_info["is_veg"],
                is_bestseller=item_info["is_bestseller"],
                is_available=True,
                preparation_time=item_info["prep_time"],
                calories=item_info["calories"],
                dietary_tags=item_info["tags"],
                spice_level=item_info["spice"],
                image_url=item_info["img"]
            )
            db.add(menu_item)
            db.commit()
            db.refresh(menu_item)
            saved_items.append(menu_item)

            for group_info in item_info.get("customizations", []):
                group = MenuCustomizationGroup(
                    item_id=menu_item.id,
                    group_name=group_info["group_name"],
                    is_required=group_info["is_required"],
                    min_select=group_info["min_select"],
                    max_select=group_info["max_select"]
                )
                db.add(group)
                db.commit()
                db.refresh(group)

                for opt_info in group_info["options"]:
                    opt = MenuCustomizationOption(
                        group_id=group.id,
                        name=opt_info["name"],
                        additional_price=opt_info["price"],
                        is_default=opt_info["is_default"]
                    )
                    db.add(opt)
                db.commit()

        # 6. Active Table Sessions & Demonstration Orders for Kitchen and Floor
        # Table T-01 has an active session and an order being prepared
        sess_t1 = TableSession(
            table_id=created_tables[0].id,
            customer_name="Rohan Mehta",
            customer_phone="+91 99887 76655",
            guest_count=2,
            session_token="sess_t01_active_token_123",
            is_active=True
        )
        db.add(sess_t1)
        db.commit()
        db.refresh(sess_t1)
        created_tables[0].current_session_id = sess_t1.id
        db.commit()

        # Order 1 for Table T-01 (PREPARING in Kitchen)
        ord1 = Order(
            order_number="ORD-20261109-001",
            restaurant_id=restaurant.id,
            table_id=created_tables[0].id,
            session_id=sess_t1.id,
            customer_name="Rohan Mehta",
            customer_phone="+91 99887 76655",
            status=OrderStatus.PREPARING,
            priority=OrderPriority.NORMAL,
            subtotal=900.0,
            tax_amount=45.0,
            service_charge=45.0,
            tip_amount=50.0,
            total_amount=1040.0,
            payment_status=PaymentStatus.UNPAID,
            special_instructions="Make the paneer extra crispy please.",
            estimated_prep_time=20
        )
        db.add(ord1)
        db.commit()
        db.refresh(ord1)

        ord1_items = [
            OrderItem(
                order_id=ord1.id,
                menu_item_id=saved_items[0].id,
                item_name=saved_items[0].name,
                unit_price=380.0,
                quantity=1,
                total_price=380.0,
                customizations_json=json.dumps([{"group_name": "Spice Level", "option_name": "Extra Spicy", "additional_price": 0.0}]),
                special_instructions="Extra crispy",
                status="COOKING"
            ),
            OrderItem(
                order_id=ord1.id,
                menu_item_id=saved_items[4].id,
                item_name=saved_items[4].name,
                unit_price=520.0,
                quantity=1,
                total_price=520.0,
                customizations_json=json.dumps([{"group_name": "Portion & Meat Choice", "option_name": "Boneless Chicken", "additional_price": 0.0}]),
                special_instructions="",
                status="COOKING"
            )
        ]
        db.add_all(ord1_items)

        ord1_history = [
            OrderStatusHistory(order_id=ord1.id, previous_status=None, new_status="PLACED", changed_by="Customer App"),
            OrderStatusHistory(order_id=ord1.id, previous_status="PLACED", new_status="ACCEPTED", changed_by="Chef Kabir Sen"),
            OrderStatusHistory(order_id=ord1.id, previous_status="ACCEPTED", new_status="PREPARING", changed_by="Chef Kabir Sen")
        ]
        db.add_all(ord1_history)

        # Service request for Table T-01
        req1 = ServiceRequest(
            restaurant_id=restaurant.id,
            table_id=created_tables[0].id,
            request_type=ServiceRequestType.WATER,
            status=ServiceRequestStatus.PENDING,
            customer_notes="Please bring 1 bottle of sparkling water."
        )
        db.add(req1)

        # Order 2 for Table T-03 (PLACED / NEW ORDER in Kitchen)
        ord2 = Order(
            order_number="ORD-20261109-002",
            restaurant_id=restaurant.id,
            table_id=created_tables[2].id,
            customer_name="Simran Kaur",
            customer_phone="+91 98765 11223",
            status=OrderStatus.PLACED,
            priority=OrderPriority.HIGH,
            subtotal=1000.0,
            tax_amount=50.0,
            service_charge=50.0,
            tip_amount=0.0,
            total_amount=1100.0,
            payment_status=PaymentStatus.UNPAID,
            special_instructions="Serve fast please, we have a movie at 9 PM.",
            estimated_prep_time=15
        )
        db.add(ord2)
        db.commit()
        db.refresh(ord2)

        ord2_items = [
            OrderItem(
                order_id=ord2.id,
                menu_item_id=saved_items[1].id,
                item_name=saved_items[1].name,
                unit_price=440.0,
                quantity=1,
                total_price=440.0,
                status="QUEUED"
            ),
            OrderItem(
                order_id=ord2.id,
                menu_item_id=saved_items[8].id,
                item_name=saved_items[8].name,
                unit_price=560.0,
                quantity=1,
                total_price=560.0,
                status="QUEUED"
            )
        ]
        db.add_all(ord2_items)
        db.add(OrderStatusHistory(order_id=ord2.id, previous_status=None, new_status="PLACED", changed_by="Customer App"))

        # Order 3 for Table T-04 (READY and BILL REQUESTED)
        ord3 = Order(
            order_number="ORD-20261109-003",
            restaurant_id=restaurant.id,
            table_id=created_tables[3].id,
            customer_name="Amitabh Sengupta",
            customer_phone="+91 97654 32109",
            status=OrderStatus.SERVED,
            priority=OrderPriority.NORMAL,
            subtotal=1560.0,
            tax_amount=78.0,
            service_charge=78.0,
            tip_amount=100.0,
            total_amount=1816.0,
            payment_status=PaymentStatus.UNPAID,
            special_instructions="Gentle spice.",
            estimated_prep_time=25,
            actual_prep_time=22
        )
        db.add(ord3)
        db.commit()
        db.refresh(ord3)

        bill3 = Bill(
            bill_number="INV-20261109-003",
            restaurant_id=restaurant.id,
            order_id=ord3.id,
            table_id=created_tables[3].id,
            subtotal=1560.0,
            tax_percentage=5.0,
            tax_amount=78.0,
            service_charge_percentage=5.0,
            service_charge=78.0,
            tip_amount=100.0,
            discount_amount=0.0,
            final_amount=1816.0,
            status=BillStatus.UNPAID
        )
        db.add(bill3)

        # Service request for Table T-04
        req3 = ServiceRequest(
            restaurant_id=restaurant.id,
            table_id=created_tables[3].id,
            request_type=ServiceRequestType.BILL,
            status=ServiceRequestStatus.PENDING,
            customer_notes="Ready for check, split bill requested."
        )
        db.add(req3)

        # 7. Add some historical completed orders over the past 7 days for realistic analytics
        now = datetime.now(timezone.utc)
        for days_ago in range(1, 8):
            dt = now - timedelta(days=days_ago)
            order_count_for_day = 8 + (days_ago % 4) * 3
            for i in range(order_count_for_day):
                sample_subtotal = 650.0 + (i * 180.0) % 1200.0
                tax = sample_subtotal * 0.05
                sc = sample_subtotal * 0.05
                total = sample_subtotal + tax + sc

                hist_ord = Order(
                    order_number=f"ORD-PAST-{days_ago}-{i:02d}",
                    restaurant_id=restaurant.id,
                    table_id=created_tables[i % len(created_tables)].id,
                    customer_name=f"Guest {days_ago}_{i}",
                    status=OrderStatus.COMPLETED,
                    priority=OrderPriority.NORMAL,
                    subtotal=sample_subtotal,
                    tax_amount=tax,
                    service_charge=sc,
                    tip_amount=50.0 if i % 2 == 0 else 0.0,
                    total_amount=total + (50.0 if i % 2 == 0 else 0.0),
                    payment_status=PaymentStatus.PAID,
                    estimated_prep_time=20,
                    actual_prep_time=18,
                    created_at=dt + timedelta(hours=(12 + (i % 10))),
                    updated_at=dt + timedelta(hours=(13 + (i % 10)))
                )
                db.add(hist_ord)
                db.commit()
                db.refresh(hist_ord)

                hist_bill = Bill(
                    bill_number=f"INV-PAST-{days_ago}-{i:02d}",
                    restaurant_id=restaurant.id,
                    order_id=hist_ord.id,
                    table_id=hist_ord.table_id,
                    subtotal=sample_subtotal,
                    tax_percentage=5.0,
                    tax_amount=tax,
                    service_charge_percentage=5.0,
                    service_charge=sc,
                    tip_amount=hist_ord.tip_amount,
                    discount_amount=0.0,
                    final_amount=hist_ord.total_amount,
                    status=BillStatus.PAID,
                    created_at=hist_ord.created_at
                )
                db.add(hist_bill)
                db.commit()
                db.refresh(hist_bill)

                hist_payment = Payment(
                    bill_id=hist_bill.id,
                    amount=hist_ord.total_amount,
                    payment_method=PaymentMethod.RAZORPAY if i % 2 == 0 else PaymentMethod.CARD,
                    transaction_id=f"txn_sandbox_{days_ago}_{i}_{int(datetime.now().timestamp())}",
                    status=PaymentRecordStatus.SUCCESS,
                    created_at=hist_ord.created_at
                )
                db.add(hist_payment)

        # 8. Sample Reservations
        reservations_data = [
            {
                "name": "Dr. Sameer Kapoor",
                "email": "sameer.k@example.com",
                "phone": "+91 99112 23344",
                "count": 4,
                "date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                "time": "08:00 PM",
                "table_id": created_tables[5].id,
                "status": ReservationStatus.CONFIRMED,
                "notes": "Anniversary celebration, window table preferred."
            },
            {
                "name": "Meera Nambiar",
                "email": "meera.n@example.com",
                "phone": "+91 98223 34455",
                "count": 6,
                "date": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
                "time": "07:30 PM",
                "table_id": None,
                "status": ReservationStatus.PENDING,
                "notes": "Family dinner, 2 high chairs needed."
            }
        ]
        for res_item in reservations_data:
            res = Reservation(
                restaurant_id=restaurant.id,
                customer_name=res_item["name"],
                customer_email=res_item["email"],
                customer_phone=res_item["phone"],
                guest_count=res_item["count"],
                reservation_date=res_item["date"],
                reservation_time=res_item["time"],
                table_id=res_item["table_id"],
                status=res_item["status"],
                special_requests=res_item["notes"]
            )
            db.add(res)

        db.commit()
        print("Database seeded successfully with rich realistic restaurant data!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
