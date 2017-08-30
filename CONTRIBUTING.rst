=======================
Contributing to TIoPPy 
=======================

Thank you for considering contributing to ttproto!

.. contents:: Table of content

Git workflow - Merge request guidelines
=======================================


If you can, please submit a merge request with the fix or improvements
including tests. If you don't know how to fix the issue but can write a test
that exposes the issue we will accept that as well. In general bug fixes that
include a regression test are merged quickly while new features without proper
tests are least likely to receive timely feedback. The workflow to make a merge
request is as follows:


.. [#] Fork the project into your personal space on gitlab
.. [#] Create a feature branch, branch away from master (if it's a fix) or develop (if it's a new feature or doc)
.. [#] Write tests, code and/or doc
.. [#] If you have multiple commits please combine them into a few logically organized commits by squashing them
.. [#] Push the commit(s) to your fork
.. [#] Submit a merge request (MR) to the master branch / develop branch (depending if it's a fix or new feature)

Some other comments:

.. [#] The MR title should describe the change you want to make
.. [#] The MR description should give a motive for your change and the method you used to achieve it.
.. [#] If you are proposing core/substantial changes to the tools please create an issue first to discuss it beforehand.
.. [#] Mention the issue(s) your merge request solves, using the Solves #XXX or Closes #XXX syntax.
.. [#] Please keep the change in a single MR as small as possible.
.. [#] For examples of feedback on merge requests please look at already closed merge requests.
.. [#] Merging will be done by main maintainer after reviewing the changes.

When having your code reviewed and when reviewing merge requests please take the
code review guidelines into account.

