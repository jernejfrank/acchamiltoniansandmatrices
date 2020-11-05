from __future__ import division, print_function

from sympy import (
    Add,
    Derivative,
    Expr,
    Function,
    Mul,
    Pow,
    Rational,
    S,
    simplify,
    symbols,
    sympify,
)
from sympy.core.decorators import _sympifyit, call_highest_priority
from sympy.core.function import UndefinedFunction
from sympy.physics.quantum import Operator
from sympy.physics.quantum.dagger import Dagger
from sympy.physics.quantum.operator import Operator
from sympy.printing.latex import print_latex
from sympy.printing.pretty.stringpict import prettyForm
from termcolor import colored


def debugprint(obj):
    """
    Helper function to debug the code.
    """

    try:
        print(obj.args)
    except:
        pass
    try:
        print(vars(obj.args[1]))
    except:
        pass


def orderArgs(cls, A, B):
    """
    Order the arguments using Sympy compare.

    This is used to order the Poisson Bracket arguments
    taking the anti-symmetry of the bracket into account.

    Important note:
    ---------------
    When this method is called, the object is not of cls
    Expr but of cls Mul. Therefore we need to add the phase-space
    coordinates manually after this method has returned the Mul obj.

    See __new__ method in the PoissonBracket class.

    Arguments:
    ----------
    cls: cls
        class used in the second argument of the Mul Obj
    A : argument one
    B : argument two

    Returns:
    --------
    In case the order of A and B needs to be reversed it will
    return Mul(-1, cls(B,A)), otherwise None is returned.

    """
    if isinstance(A, UndefinedFunction):
        # create temp symbol to be able to
        # compare undefined functions
        tmp = symbols("tmp")

        if isinstance(B, UndefinedFunction):
            # both are undefined functions
            if A(tmp).compare(B(tmp)) == 1:
                return S.NegativeOne * cls(B, A)

        elif A(tmp).compare(B) == 1:
            # A is an undefined function
            return S.NegativeOne * cls(B, A)

    elif isinstance(B, UndefinedFunction):
        # create temp symbol to be able to
        # compare undefined functions
        tmp = symbols("tmp")
        if A.compare(B(tmp)) == 1:
            # B is an undefined function
            return S.NegativeOne * cls(B, A)
    else:
        # nor A nor B is undefined, direct comparison
        # is performed
        if A.compare(B) == 1:
            return S.NegativeOne * cls(B, A)
        return None


class PoissonBracket(Expr):
    """ Class for doing Poisson Brackets - classical mechanics"""

    _op_priority = 11.0
    _is_commutative = False

    def __new__(cls, f, g, **kwargs):
        """
        Create new object.

        Arguments:
        ---------
        cls: cls
        f:  UndefinedFunction | Function | PoissonBracket
            argument one

        g: UndefinedFunction | Function | PoissonBracket
            argument two

        kwargs: used for setting the phase-space coordinates
            coords : list
            mom : list
        """
        # make sure arguments are Sympy
        A = sympify(f)
        B = sympify(g)

        # if args are equal return Zero
        if A == B:
            return S.Zero

        # if either argument is a number return Zero
        elif A.is_number or B.is_number:
            return S.Zero

        # order the arguments
        obj = orderArgs(cls, A, B)

        if obj is not None:
            # manually set the phase-space coordinates
            # Mul overwrites - see orderArgs for more
            obj.args[1].coords = kwargs.get("coords", None)
            obj.args[1].mom = kwargs.get("mom", None)
            return obj
        else:
            # create new Expr obj
            obj = Expr.__new__(cls, A, B)
            obj.A = A
            obj.B = B
            return obj

    def __init__(self, f, g, **kwargs):
        # set the phase-space coordinates
        self.coords = kwargs.get("coords", None)
        self.mom = kwargs.get("mom", None)

    def _eval_derivative(self, symbol):
        """Derivative of a PoissonBracket"""

        new_expr = self.doit().diff(symbol)

        return new_expr

    def doit(self, **hints):
        """ Perform the Poisson Bracket"""
        # load the phase-space coordinates
        c = self.coords
        m = self.mom

        # if there is a problem with
        # the phase-space coordinates
        # return self and print issue
        if m is None or c is None:
            print(colored("Nothing to evaluate - missing coordinates and momenta!", "red"))
            return self
        elif len(c) != len(m):
            print(
                colored("Nothing to evaluate - uneven number of coordinates and momenta!", "red")
            )
            return self

        # load the bracket arguments
        A = self.args[0]
        B = self.args[1]

        # if one of the args is a Poisson Bracket
        # the outer c and m need to be used
        # we therefore overwrite them
        if isinstance(A, PoissonBracket):
            A.coords = c
            A.mom = m
        if isinstance(B, PoissonBracket):
            B.coords = c
            B.mom = m

        # calculate the Poisson Bracket
        hp = S(0)
        for qi, pi in zip(c, m):
            hp += A.diff(qi) * B.diff(pi)
            hp -= A.diff(pi) * B.diff(qi)

        return hp

    def _eval_expand_commutator(self, **hints):
        """ Method to expand Poisson Brackets"""
        # TODO: Jacobi Id

        A = self.args[0]
        B = self.args[1]

        if isinstance(A, Add):
            # {A + B, C}  ->  {A, C} + {B, C}
            sargs = []
            for term in A.args:
                comm = PoissonBracket(term, B)
                if isinstance(comm, PoissonBracket):
                    comm = comm._eval_expand_commutator()
                sargs.append(comm)
            return Add(*sargs)

        elif isinstance(B, Add):
            # {A, B + C}  ->  {A, B} + {A, C}
            sargs = []
            for term in B.args:
                comm = PoissonBracket(A, term)
                if isinstance(comm, PoissonBracket):
                    comm = comm._eval_expand_commutator()
                sargs.append(comm)
            return Add(*sargs)

        elif isinstance(A, Mul):
            # {A*B, C} -> A*{B, C} + {A, C}*B
            a = A.args[0]
            b = Mul(*A.args[1:])
            c = B
            comm1 = PoissonBracket(b, c)
            comm2 = PoissonBracket(a, c)
            if isinstance(comm1, PoissonBracket):
                comm1 = comm1._eval_expand_commutator()
            if isinstance(comm2, PoissonBracket):
                comm2 = comm2._eval_expand_commutator()
            first = Mul(a, comm1)
            second = Mul(comm2, b)
            return Add(first, second)

        elif isinstance(B, Mul):
            # {A, B*C} -> {A, B}*C + B*{A, C}
            a = A
            b = B.args[0]
            c = Mul(*B.args[1:])
            comm1 = PoissonBracket(a, b)
            comm2 = PoissonBracket(a, c)
            if isinstance(comm1, PoissonBracket):
                comm1 = comm1._eval_expand_commutator()
            if isinstance(comm2, PoissonBracket):
                comm2 = comm2._eval_expand_commutator()
            first = Mul(comm1, c)
            second = Mul(b, comm2)
            return Add(first, second)

        elif isinstance(A, Pow):
            # {A**n, C} -> A**(n - 1)*[A, C] + A**(n - 2)*[A, C]*A + ... + [A, C]*A**(n-1)
            return self._expand_pow(A, B, 1)
        elif isinstance(B, Pow):
            # [A, C**n] -> C**(n - 1)*[C, A] + C**(n - 2)*[C, A]*C + ... + [C, A]*C**(n-1)
            return self._expand_pow(B, A, -1)
        return self
