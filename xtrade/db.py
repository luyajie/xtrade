from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class OrderModel(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(10), nullable=False)
    price = db.Column(db.Float, nullable=True)  # None for market-*
    timestamp = db.Column(db.String(20), nullable=False)


class TradeModel(db.Model):
    __tablename__ = 'trades'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, nullable=False)
    order_type = db.Column(db.String(10), nullable=False)
    price = db.Column(db.Float, nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.String(20), nullable=False)
