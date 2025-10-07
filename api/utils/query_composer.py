from __future__ import annotations

from loguru import logger
import json
from lark import Lark, v_args, Transformer
from typing import List, Dict, Any, Tuple, Union, TypedDict, Literal, Optional, Sequence
import warnings
import datetime
from enum import Enum  
from pydantic import BaseModel
from abc import ABC, abstractmethod
import traceback
from email_validator import validate_email, EmailNotValidError
import re

class Expr(BaseModel):
    """Base class for all expressions."""

    def accept(self, visitor: Visitor) -> Any:
        """Accept a visitor.

        Args:
            visitor: visitor to accept.

        Returns:
            result of visiting.
        """
        return getattr(visitor, f"visit_{_to_snake_case(self.__class__.__name__)}")(
            self
        )

class FilterDirective(Expr, ABC):
    """Filtering expression."""

class ISO8601Date(TypedDict):
    """A date in ISO 8601 format (YYYY-MM-DD)."""

    date: str
    type: Literal["date"]

class ISO8601DateTime(TypedDict):
    """A datetime in ISO 8601 format (YYYY-MM-DDTHH:MM:SS)."""

    datetime: str
    type: Literal["datetime"]

class Operator(str, Enum):
    """Enumerator of the operations."""

    AND = "and"
    OR = "or"
    NOT = "not"

class Operation(FilterDirective):
    """Logical operation over other directives."""

    operator: Operator
    """The operator to use."""
    arguments: list[FilterDirective]
    """The arguments to the operator."""

    def __init__(
        self, operator: Operator, arguments: list[FilterDirective], **kwargs: Any
    ) -> None:
        """Create an Operation.

        Args:
            operator: The operator to use.
            arguments: The arguments to the operator.
        """
        # super exists from BaseModel
        super().__init__(  # type: ignore[call-arg]
            operator=operator, arguments=arguments, **kwargs
        )

class Comparator(str, Enum):
    """Enumerator of the comparison operators."""

    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    CONTAIN = "contain"
    LIKE = "like"
    IN = "in"
    NIN = "nin"

class Visitor(ABC):
    """Defines interface for IR translation using a visitor pattern."""

    allowed_comparators: Optional[Sequence[Comparator]] = None
    """Allowed comparators for the visitor."""
    allowed_operators: Optional[Sequence[Operator]] = None
    """Allowed operators for the visitor."""

    def _validate_func(self, func: Union[Operator, Comparator]) -> None:
        if (
            isinstance(func, Operator)
            and self.allowed_operators is not None
            and func not in self.allowed_operators
        ):
            msg = (
                f"Received disallowed operator {func}. Allowed "
                f"comparators are {self.allowed_operators}"
            )
            raise ValueError(msg)
        if (
            isinstance(func, Comparator)
            and self.allowed_comparators is not None
            and func not in self.allowed_comparators
        ):
            msg = (
                f"Received disallowed comparator {func}. Allowed "
                f"comparators are {self.allowed_comparators}"
            )
            raise ValueError(msg)

    @abstractmethod
    def visit_operation(self, operation: Operation) -> Any:
        """Translate an Operation.

        Args:
            operation: Operation to translate.
        """

    @abstractmethod
    def visit_comparison(self, comparison: Comparison) -> Any:
        """Translate a Comparison.

        Args:
            comparison: Comparison to translate.
        """

    @abstractmethod
    def visit_structured_query(self, structured_query: StructuredQuery) -> Any:
        """Translate a StructuredQuery.

        Args:
            structured_query: StructuredQuery to translate.
        """
class Comparison(FilterDirective):
    """Comparison to a value."""

    comparator: Comparator
    """The comparator to use."""
    attribute: str
    """The attribute to compare."""
    value: Any
    """The value to compare to."""

    def __init__(
        self, comparator: Comparator, attribute: str, value: Any, **kwargs: Any
    ) -> None:
        """Create a Comparison.

        Args:
            comparator: The comparator to use.
            attribute: The attribute to compare.
            value: The value to compare to.
        """
        # super exists from BaseModel
        super().__init__(  # type: ignore[call-arg]
            comparator=comparator, attribute=attribute, value=value, **kwargs
        )

GRAMMAR = r"""
    ?program: func_call
    ?expr: func_call
        | value

    func_call: CNAME "(" [args] ")"

    ?value: SIGNED_INT -> int
        | SIGNED_FLOAT -> float
        | DATE -> date
        | DATETIME -> datetime
        | list
        | string
        | ("false" | "False" | "FALSE") -> false
        | ("true" | "True" | "TRUE") -> true

    args: expr ("," expr)*
    DATE.2: /["']?(\d{4}-[01]\d-[0-3]\d)["']?/
    DATETIME.2: /["']?\d{4}-[01]\d-[0-3]\dT[0-2]\d:[0-5]\d:[0-5]\d[Zz]?["']?/
    string: /'[^']*'/ | ESCAPED_STRING
    list: "[" [args] "]"

    %import common.CNAME
    %import common.ESCAPED_STRING
    %import common.SIGNED_FLOAT
    %import common.SIGNED_INT
    %import common.WS
    %ignore WS
"""

@v_args(inline=True)
class QueryTransformer(Transformer):
    """Transform a query string into an intermediate representation."""
    
    def __init__(self, 
        *args:Any, 
        allowed_comparators: list[str] = ["eq", "neq", "gt", "gte", "lt", "lte", "contain", "like", "in", "nin"],
        allowed_operators: list[str] = ["and", "or", "not"],
        allowed_attributes: list[str] = ["created", "from_email"],
        **kwargs:Any):
        super().__init__(*args, **kwargs)
        self.allowed_comparators = allowed_comparators
        self.allowed_operators = allowed_operators
        self.allowed_attributes = allowed_attributes

    def program(self, *items: Any) -> Tuple:
        return items

    def func_call(self, func_name: Any, args: list) -> FilterDirective:
        func = self._match_func_name(str(func_name))
        if isinstance(func, Comparator):
            if self.allowed_attributes and args[0] not in self.allowed_attributes:
                raise ValueError(
                    f"Received invalid attributes {args[0]}. Allowed attributes are "
                    f"{self.allowed_attributes}"
                )
            return Comparison(comparator=func, attribute=args[0], value=args[1])
        elif len(args) == 1 and func in (Operator.AND, Operator.OR):
            return args[0]
        else:
            return Operation(operator=func, arguments=args)

    def _match_func_name(self, func_name: str) -> Union[Operator, Comparator]:
        if func_name in set(Comparator):
            if self.allowed_comparators is not None:
                if func_name not in self.allowed_comparators:
                    raise ValueError(
                        f"Received disallowed comparator {func_name}. Allowed "
                        f"comparators are {self.allowed_comparators}"
                    )
            return Comparator(func_name)
        elif func_name in set(Operator):
            if self.allowed_operators is not None:
                if func_name not in self.allowed_operators:
                    raise ValueError(
                        f"Received disallowed operator {func_name}. Allowed operators"
                        f" are {self.allowed_operators}"
                    )
            return Operator(func_name)
        else:
            raise ValueError(
                f"Received unrecognized function {func_name}. Valid functions are "
                f"{list(Operator) + list(Comparator)}"
            )

    def args(self, *items: Any) -> tuple:
        return items

    def false(self) -> bool:
        return False

    def true(self) -> bool:
        return True

    def list(self, item: Any) -> list:
        if item is None:
            return []
        return list(item)

    def int(self, item: Any) -> int:
        return int(item)

    def float(self, item: Any) -> float:
        return float(item)

    def date(self, item: Any) -> ISO8601Date:
        item = str(item).strip("\"'")
        try:
            datetime.datetime.strptime(item, "%Y-%m-%d")
        except ValueError:
            warnings.warn(
                "Dates are expected to be provided in ISO 8601 date format "
                "(YYYY-MM-DD)."
            )
        return {"date": item, "type": "date"}

    def datetime(self, item: Any) -> ISO8601DateTime:
        item = str(item).strip("\"'")
        try:
            # Parse full ISO 8601 datetime format
            datetime.datetime.strptime(item, "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            try:
                datetime.datetime.strptime(item, "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                raise ValueError(
                    "Datetime values are expected to be in ISO 8601 format."
                )
        return {"datetime": item, "type": "datetime"}

    def string(self, item: Any) -> str:
        # Remove escaped quotes
        return str(item).strip("\"'")

class QueryParams(BaseModel):
    timestampBefore: Optional[int] = None
    timestampAfter: Optional[int] = None
    fromEmail: Optional[str] = None
    sort: Optional[Literal["desc", "asc", "NO_SORT"]] = None 

class QueryComposer:
    
    def __init__(self):
        self.parser = Lark(GRAMMAR, parser='lalr', start='program', transformer=QueryTransformer())

    def parse_date_to_milliseconds(self, date: str) -> int:
        return int(datetime.datetime.strptime(date, "%Y-%m-%d").timestamp() * 1000)
    
    def fix_filter_expressions(self, filter_expression: str) -> list[str]:
        pattern = r'(?<!")\b(created|from_email)\b(?!")'
        def quote_param(match):
            # Wrap the matched word with quotes
            return f'"{match.group(1)}"'

        return re.sub(pattern, quote_param, filter_expression)

    def compose(self, query_json: dict) -> QueryParams:
        try:
            query_params = QueryParams()
            if "sort" in query_json:
                if query_json["sort"].startswith("desc"):
                    query_params.sort = "desc"
                elif query_json["sort"].startswith("asc"):
                    query_params.sort = "asc"

            if "filter" in query_json and query_json["filter"] != "NO_FILTER":
                filter_expression = self.fix_filter_expressions(query_json["filter"])
                output = self.parser.parse(filter_expression)
            
                if isinstance(output, Operation):
                    for arg in output.arguments:
                        attr = arg.attribute
                        if attr in ["created"]:
                            value = arg.value
                            if  (arg.comparator == Comparator.GTE or arg.comparator == Comparator.GT):
                                if "type" in value:
                                    query_params.timestampAfter = self.parse_date_to_milliseconds(value["date"]) 
                                else:
                                    query_params.timestampAfter = self.parse_date_to_milliseconds(value)
                            elif (arg.comparator == Comparator.LT or arg.comparator == Comparator.LTE):
                                if "type" in value:
                                    query_params.timestampBefore = self.parse_date_to_milliseconds(value["date"])
                                else:
                                    query_params.timestampBefore = self.parse_date_to_milliseconds(value)
                        elif attr in ["from_email"]:
                            try:
                                emailinfo = validate_email(arg.value, check_deliverability=False)
                                query_params.fromEmail = emailinfo.normalized
                            except EmailNotValidError as e:
                                logger.warning(f"Invalid email: {e}")
                                query_params.fromEmail = arg.value
            
                elif isinstance(output, Comparison):
                    attr = output.attribute
                    if attr in ["created"]:
                        value = output.value
                        if (output.comparator == Comparator.GTE or output.comparator == Comparator.GT):
                            if "type" in value:
                                query_params.timestampAfter = self.parse_date_to_milliseconds(value["date"])
                            else:
                                query_params.timestampAfter = self.parse_date_to_milliseconds(value)
                        elif (output.comparator == Comparator.LT or output.comparator == Comparator.LTE):
                            if "type" in value:
                                query_params.timestampBefore = self.parse_date_to_milliseconds(value["date"])
                            else:
                                query_params.timestampBefore = self.parse_date_to_milliseconds(value)
                    elif attr in ["from_email"]:
                        try:
                            emailinfo = validate_email(output.value, check_deliverability=False)
                            query_params.fromEmail = emailinfo.normalized
                        except EmailNotValidError as e:
                            logger.warning(f"Invalid email: {e}")

                            # query_params.fromEmail = output.value
                else:
                    raise ValueError(f"Invalid query: {query_json}")

            return query_params
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f"Error parsing query: {e}")
            return None

if __name__ == "__main__":
    query_json = {"query":"electricity bill","filter":"and(gte(\"created\", \"2024-04-01\"), lt(\"created\", \"2024-05-01\"))","sort":"NO_SORT"}
    query_json = { "query": "invitation", "filter": "gt(\"created\", \"2025-02-01\")", "sort": "desc(\"created\")" }
    query_json = { "query": "email", "filter": "and(eq(\"from_email\", \"igor@mail.io\"))", "sort": "desc(\"created\")" }
    query_json = {'query': 'attachment', 'filter': 'eq(from_email, \"igor@mail.io\")', 'sort': 'NO_SORT'}
    query_json = {'query': 'digitalocean bill', 'filter': 'and(gte(created, "2025-03-01"), lte(created, "2025-03-31"))', 'sort': 'NO_SORT'}
    composer = QueryComposer()
    logger.debug(f"query_json['query']: {query_json['query']}")
    logger.debug(f"query_json['sort']: {query_json['sort']}")
    if query_json["filter"] != "NO_FILTER":
        query_params = composer.compose(query_json)
        logger.debug(f"query_params: {query_params}")

        
