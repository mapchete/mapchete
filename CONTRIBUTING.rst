=========================
Contributing to mapchete
=========================

First off, thanks for considering contributing to ``mapchete``! We welcome all kinds of contributions, from reporting bugs and suggesting features to submitting pull requests with new code or documentation improvements.

This document provides guidelines to help make the contribution process smooth and effective for everyone.


Ways to Contribute
==================

There are many ways you can contribute to the project:

* 🐛 **Reporting Bugs**: If you find a bug, please create a `GitHub Issue <https://github.com/mapchete/mapchete/issues>`_ to let us know.
* 💡 **Suggesting Enhancements**: Have an idea for a new feature or an improvement to an existing one? Feel free to open an issue to discuss it.
* 📖 **Improving Documentation**: If you find parts of the documentation that are unclear or incomplete, you can submit a pull request to improve them.
* 💻 **Submitting Code**: You can contribute bug fixes, new features, or new drivers by submitting a pull request.


Reporting Bugs
==============

When creating a bug report, please include as many details as possible. A good bug report should include:

* ``mapchete`` version you are using (e.g., from ``mapchete --version``).
* Python and OS version.
* Clear steps to reproduce the bug.
* What you expected to happen versus what actually happened.
* Any error messages or tracebacks you received.


Submitting Pull Requests
========================

If you'd like to contribute code or documentation, please follow these steps.

**1. Set Up Your Environment**

First, fork the repository on GitHub and clone it to your local machine.

.. code-block:: bash

   git clone https://github.com/your-username/mapchete.git
   cd mapchete

**2. Create a Branch**

Create a new branch for your changes. Choose a descriptive name, like ``fix-hillshade-bug`` or ``feature-new-driver``.

.. code-block:: bash

   git checkout -b your-branch-name

**3. Make Your Changes**

Write your code! As you work, make sure your code follows our style guidelines. We use **black** for formatting and **flake8** for linting. You can run them locally before committing:

.. code-block:: bash

   # Auto-format your code
   black .
   # Check for style issues
   flake8 mapchete

**4. Write Tests**

We use **pytest** for testing. If you're adding a new feature or fixing a bug, please add a test to cover your changes. Tests are located in the ``test/`` directory.

You can run the full test suite with this command:

.. code-block:: bash

   pytest

**5. Update Documentation**

If your changes affect the public API or add new functionality, please update the documentation in the ``docs/`` directory.

**6. Submit Your Pull Request**

Once you're happy with your changes and all tests are passing, commit your work and push it to your fork.

.. code-block:: bash

   git commit -m "A brief, descriptive commit message"
   git push origin your-branch-name

Finally, open a **Pull Request** from your fork on GitHub. In the PR description, explain the "why" and "what" of your changes. If your PR addresses an open issue, please reference it using ``Closes #issue-number``.

Thank you for helping make ``mapchete`` better!