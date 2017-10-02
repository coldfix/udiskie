Hacking
-------

*udiskie* is developed on github_. Feel free to contribute patches as pull
requests here.

Try to be consistent with the PEP8_ guidelines. Add `unit tests`_ if possible.
`Dependency injection`_ is a great pattern to keep modules flexible and
testable.

Commits should be reversible, independent units if possible. Use descriptive
titles and also add an explaining commit message unless the modification is
trivial. See also: `A Note About Git Commit Messages`_.

Further resources:

- `UDisks1 API`_
- `UDisks2 API`_
- `PyGObject APIs`_

.. _github: https://github.com/coldfix/udiskie
.. _PEP8: http://www.python.org/dev/peps/pep-0008/
.. _`unit tests`: http://docs.python.org/2/library/unittest.html
.. _`Dependency injection`: http://www.youtube.com/watch?v=RlfLCWKxHJ0
.. _`A Note About Git Commit Messages`: http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html

.. _`UDisks1 API`: http://udisks.freedesktop.org/docs/1.0.5/
.. _`UDisks2 API`: http://udisks.freedesktop.org/docs/latest/
.. _`PyGObject APIs`: http://lazka.github.io/pgi-docs/index.html


Roadmap
-------

For the next udiskie versions, I am mainly concerned with quality assurance
and stability. For one this means reducing the number of supported runtime
configurations and make the remaining easier to test, i.e.:

- **drop support for python2** to avoid unicode issues and make use of the new
  asyncio module which provides better error handling (stack traces!) than the
  current solution.
- **drop support for udisks1**. The udisks1 API is rather unfit for the
  asynchronous nature of the problem which has led to numerous bugs and
  problems (plenty more probably waiting to be discovered as we speak)
- **add automated tests**. needed desperately…
