TOOLS_DEFINITION = [
    {
        "name": "search_documents",
        "description": (
            "Perform semantic search against PDF support policies, cancellation SOPs, "
            "and signed customer agreements in the database. Restricted to general and "
            "own-account scoped files for customers, while internal users can query everything. "
            "Filters out DEPRECATED documents by default unless 'include_deprecated' is True."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query containing keywords or problem descriptions."
                },
                "include_deprecated": {
                    "type": "boolean",
                    "description": "Whether to search historical and deprecated policies (internal users only). Defaults to False."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "query_structured_data",
        "description": (
            "Lookup records from accounts, orders, or tickets tables. "
            "Allows running business math calculations (policy overrides, fees, credit amounts) "
            "on retrieved orders."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity": {
                    "type": "string",
                    "enum": ["account", "order", "ticket"],
                    "description": "The table entity to query: 'account', 'order', or 'ticket'."
                },
                "filters": {
                    "type": "object",
                    "description": "Filtering parameters. Examples: {'order_id': 'ORD-101'}, {'carrier': 'ShipFast'}, {'status': 'BOOKED'}, {'ticket_id': 'TKT-203'}."
                },
                "run_calculation": {
                    "type": "string",
                    "enum": ["cancellation", "service_credit"],
                    "description": "Run and attach policy calculation results ('cancellation' or 'service_credit') to each order record."
                }
            },
            "required": ["entity", "filters"]
        }
    },
    {
        "name": "propose_action",
        "description": (
            "Propose a state-changing operation (like cancelling an order, issuing a service credit, "
            "or filing a ticket escalation). This drafts a proposal that is saved in a PENDING state "
            "until confirmed by the user via /chat/confirm."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "enum": ["CANCEL_ORDER", "ISSUE_CREDIT", "ESCALATE_TICKET"],
                    "description": "The type of action to draft."
                },
                "reason": {
                    "type": "string",
                    "description": "Business justification explaining why this action is being proposed."
                },
                "order_id": {
                    "type": "string",
                    "description": "Order ID associated with the action (required for CANCEL_ORDER and ISSUE_CREDIT)."
                },
                "ticket_id": {
                    "type": "string",
                    "description": "Ticket ID associated with the action (required for ISSUE_CREDIT and ESCALATE_TICKET)."
                },
                "amount": {
                    "type": "number",
                    "description": "Optional credit or refund amount (takes computed policy default if omitted)."
                }
            },
            "required": ["action_type", "reason"]
        }
    },
    {
        "name": "get_operational_signals",
        "description": (
            "Retrieves dashboard real-time operational indicators, including count of "
            "unassigned tickets, active SLA breach violations, warning alerts, delayed order pickups, "
            "and carrier reliability scorecards."
        ),
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    }
]
