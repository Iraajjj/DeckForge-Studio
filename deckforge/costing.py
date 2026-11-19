"""Optional, fully user-configured unit economics (no implied Etsy fee rates).

One deck per order. The figures are *estimates*, excluding VAT, income tax,
returns and multi-item orders unless user includes allowances explicitly.
"""
from __future__ import annotations

from csv import DictWriter
import json
import math
from pathlib import Path

INPUT_NAME = 'pricing_scenarios.json'


def example() -> dict:
    return {
        'schema_version': 1,
        'illustrative_data_only': True,
        'currency': 'EUR',
        'retail_price': 34.00,
        'shipping_charged_to_customer': 4.90,
        'outbound_shipping_per_order': 5.20,
        'packaging_cost_per_deck': 1.30,
        'marketplace_fee_fraction': 0.08,
        'marketplace_flat_fee_per_order': 0.25,
        'payment_fee_fraction': 0.02,
        'payment_flat_fee_per_order': 0.35,
        'allowance_per_order': 0,
        'quotes': [
            {'supplier': 'ILLUSTRATIVE quote A', 'quantity': 20, 'unit_print_cost': 15.00, 'setup_cost': 0, 'inbound_shipping_total': 16.00},
            {'supplier': 'ILLUSTRATIVE quote B', 'quantity': 50, 'unit_print_cost': 12.50, 'setup_cost': 20, 'inbound_shipping_total': 30.00},
            {'supplier': 'ILLUSTRATIVE quote C', 'quantity': 100, 'unit_print_cost': 10.00, 'setup_cost': 40, 'inbound_shipping_total': 48.00},
        ],
        'notes': 'Fictional figures for testing. Replace with actual quotations and fee terms; not financial advice.'
    }


def _num(value, key: str, *, maximum=1e9) -> float:
    if not isinstance(value, (int,float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0 or value > maximum:
        raise ValueError(f'Invalid non-negative number for {key}')
    return float(value)


def calculate(input_data: dict) -> dict:
    if not isinstance(input_data,dict) or input_data.get('schema_version') != 1:
        raise ValueError('pricing_scenarios.json must have schema_version 1')
    for key in ('retail_price','shipping_charged_to_customer','outbound_shipping_per_order','packaging_cost_per_deck',
                'marketplace_fee_fraction','marketplace_flat_fee_per_order','payment_fee_fraction',
                'payment_flat_fee_per_order','allowance_per_order'):
        _num(input_data.get(key),key,maximum=1 if 'fraction' in key else 1e9)
    quotes=input_data.get('quotes')
    if not isinstance(quotes,list) or not quotes:
        raise ValueError('At least one supplier quote is required')
    currency=input_data.get('currency')
    if not isinstance(currency,str) or not 1<=len(currency)<=10:
        raise ValueError('Specify a currency code such as EUR')
    gross=input_data['retail_price']+input_data['shipping_charged_to_customer']
    fees=(gross*(input_data['marketplace_fee_fraction']+input_data['payment_fee_fraction'])+
          input_data['marketplace_flat_fee_per_order']+input_data['payment_flat_fee_per_order'])
    before_print=(gross-fees-input_data['outbound_shipping_per_order']-
                  input_data['packaging_cost_per_deck']-input_data['allowance_per_order'])
    rows=[]
    for quote in quotes:
        if not isinstance(quote,dict) or not isinstance(quote.get('supplier'),str) or not quote['supplier'].strip():
            raise ValueError('Every quote needs a supplier name')
        n=quote.get('quantity')
        if type(n) is not int or not 1<=n<=1000000:
            raise ValueError('Quote quantity must be an integer in 1..1,000,000')
        for key in ('unit_print_cost','setup_cost','inbound_shipping_total'):
            _num(quote.get(key),key)
        fixed=quote['setup_cost']+quote['inbound_shipping_total']
        variable=before_print-quote['unit_print_cost']
        profit_per_deck=variable-fixed/n
        revenue_total=gross*n
        estimated_profit=variable*n-fixed
        break_even=math.ceil(fixed/variable) if variable>0 else None
        rows.append({
            'supplier': quote['supplier'], 'quantity': n,
            'unit_print_cost': round(quote['unit_print_cost'],2),
            'estimated_unit_cost_landed': round(quote['unit_print_cost']+fixed/n,2),
            'fees_per_order': round(fees,2),
            'estimated_profit_per_deck': round(profit_per_deck,2),
            'estimated_profit_if_sold_out': round(estimated_profit,2),
            'gross_revenue_if_sold_out': round(revenue_total,2),
            'estimated_profit_margin_pct': round(100*estimated_profit/revenue_total,2) if revenue_total else None,
            'breakeven_units_for_setup_cost': break_even,
            'initial_cash_outlay_print_only': round(n*quote['unit_print_cost']+fixed,2),
        })
    return {'currency':currency,'illustrative_data_only':bool(input_data.get('illustrative_data_only')),
            'rows':rows,'assumptions':{'one_deck_per_order':True,
               'excluded':'VAT, income tax, refunds/returns, ads, storage and multi-item orders unless allowed for',
               'fees_are_user_supplied_not_current_platform_rates': True}}


def load_costs(project_dir: Path) -> dict | None:
    path=project_dir / INPUT_NAME
    if not path.is_file():return None
    return calculate(json.loads(path.read_text(encoding='utf-8')))


def write_cost_reports(data: dict, folder: Path) -> None:
    (folder/'cost_report.json').write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    rows=data['rows']
    with (folder/'cost_report.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    lines=['# DeckForge · Illustrative unit economics', '',
           '**All calculations use your supplied inputs, not verified Etsy fees or supplier quotes.**','',
           f"Currency: {data['currency']} · Assumed: one deck per order", '',
           '| Supplier | Units | Landed / deck | Profit / deck | Sell-out profit |',
           '|---|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['supplier']} | {r['quantity']} | {r['estimated_unit_cost_landed']:.2f} | {r['estimated_profit_per_deck']:.2f} | {r['estimated_profit_if_sold_out']:.2f} |")
    lines+=['', 'Excluded unless manually allowed for: VAT, taxes, returns, ads, storage, unsold inventory, and multi-item orders.',
            'This is an estimate, not an accounting or tax report.']
    (folder/'cost_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
