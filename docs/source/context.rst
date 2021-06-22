===============================
Configuring Sphinx from scratch
===============================

Version |version|

**A software demonstration by Sadie Bartholomew of the Sphinx documentation
generator.**

.. note::

   I am *not associated with the Sphinx project at all*. I have chosen
   to give a demo of Sphinx because it is a tool I have found extremely
   useful in my work in RSE roles.


Context
=======

Demo format
-----------

This is a demonstration so will be largely conducted in the terminal.

.. tip::
   
   The source and built documentation, which includes these notes,
   is (and will permanently remain) hosted on GitHub at:
   https://github.com/sadielbartholomew/sphinx-from-scratch


The Dummy Project
-----------------

``quadrilaterals``: a very simple and trivial object-oriented Python codebase
used as a placeholder for a real-life and very likely more complex project.

The codebase models categories of two-dimensional four-sided shape, which
are collectively called quadrilaterals. For each category, such as a
square or a rhombus, there are methods to calculate the area, perimeter and
number of axes of symmetry.

A diagram [#footnote1]_ showing the main classes in the dummy project, and
their inheritance hierarchy [#footnote2]_ :

.. image:: https://www.geogebra.org/resource/ncsc3adx/UDHJc4GCp82dcnjM/material-ncsc3adx.png


An example of the code in use (Python console notation):

.. code:: python

   >>> import quadrilaterals
   >>> square = quadrilaterals.Square(5)
   >>> help(square)
   Help on Square in module quadrilaterals.parallelograms.rectangles.square object:

   class Square(quadrilaterals.parallelograms.rectangles.rectangle.Rectangle, quadrilaterals.kites.rhombi.rhombus.Rhombus)
    |  Square(side_length)
    |  
    |  Base class common to all squares.

    |  Method resolution order:
    |      Square
    |      quadrilaterals.parallelograms.rectangles.rectangle.Rectangle
    

Quick links
===========

Examples of Sphinx-generated documentation
------------------------------------------

* A large but absolutely not comprehensive listing collected by the Sphinx
  team: https://www.sphinx-doc.org/en/master/examples.html
* Sphinx's own documentation (made with Sphinx, of course!):
  https://www.sphinx-doc.org/en/master/
* Python 3 documentation: https://docs.python.org/3/

Sphinx
------


Advanced
^^^^^^^^

* An "awesome" listing of extra Sphinx resources:
  https://github.com/yoloseem/awesome-sphinxdoc
* Example Sphinx extension project repositories:

  * ``sphinx-copybutton`` (button to copy code in code examples):
    https://github.com/executablebooks/sphinx-copybutton 
  * ``sphinx-toggleprompt`` (button to hide prompts and outputs in
    console-like code examples):
    https://github.com/jurasofish/sphinx-toggleprompt

Documenting projects with Sphinx
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* A nice blog post: https://medium.com/@richdayandnight/a-simple-tutorial-on-how-to-document-your-python-project-using-sphinx-and-rinohtype-177c22a15b5b
* A great post showing how to use Sphinx with other tools to document a C++
  project: https://devblogs.microsoft.com/cppblog/clear-functional-c-documentation-with-sphinx-breathe-doxygen-cmake/


.. [#footnote1] Image sourced from `this webpage
   <https://www.geogebra.org/m/bm4ja4wb>`_.

.. [#footnote2] Strictly this diagram does not capture one other
   relationship between the quadrilaterals which also exists...
