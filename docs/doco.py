##
#\mainpage Plexee Development Notes
#
#\section intro_sec Introduction
#
#These notes are intended to help developers understand and work on the Plexee Boxee application.
#* \subpage boxee_dev "Developer References for developing Boxee apps"
#* \subpage design "Design Overview"
#* \subpage coding "Coding Guidelines"
#* \subpage testing "Testing Guidelines"
#* \subpage doco "Documentation Generation"
#
#\page boxee_dev Boxee Developer References
#Alas the original pages are no more - but here's a copy from the web archive.<br>
#[Mainpage](https://web.archive.org/web/20120115092514/http://developer.boxee.tv/Main_Page)<br>
#* [Python API](https://web.archive.org/web/20120115092922/http://developer.boxee.tv/Python_API)
# * [mc](https://web.archive.org/web/20120108010208/http://developer.boxee.tv/MC_Module)
#* [Boxee UI](https://web.archive.org/web/20120115110819/http://developer.boxee.tv/Boxee_GUI_API)
# *	[UI Controls](https://web.archive.org/web/20111231234354/http://developer.boxee.tv/Controls)
#
#\page doco Documentation
#The documentation is generated using doxygen.
#Elements imported from Python 2.5 (ElementTree and UUid) are excluded
#
#\page coding Coding Guidelines
#Boxee apps run on Python 2.4
#
#\section Documenting Code
#* Comments should be compliant with Doxy
#
#\page design Design Overview
#
#\section Architecture
#The code is divided into:
# * Plugin - The entry point for the Plexee application in Boxee
# * Plexee - Manages all Boxee UI components
# * Plex, PlexGDM - Classes wrapping the Plex services
# * util - General utility functions
#
#The screens are:
# * home.xml - The main home screen
# * directory.xml - The generic screen for displaying Plex items (has a title a left hand menu and right hand content)
# * directory-album.xml - Similiar to the directory screen but displays a album of music tracks in a list
# * dialog-play.xml - The Play dialog that appears for all videos
# * dialog-settings.xml - The Settings dialog that is used to manage all Plexee application settings
# * dialog-connect.xml - The Connection dialog that appears when Plexee is connecting to Plex
# * dialog-exit.xml - The Exit dialog that appears when a user exits the home screen
# * dialog-photo.xml - The Photo dialog that appears for displaying photos
#
#\section Design Approach
#* Each screen/dialog is managed via an associated class
# * Any changes to the screen should be managed in the screen object (or parent classes)
# * A single object instance is accessible from the plexee instance
# * The python code in the XML is minimised (debugging is hard when embedded in the XML files)
# * This allows on-screen behaviour to be called on the associated screen/dialog objects
#
#\page testing Testing Guidelines
#\section Environment
#* Development testing can be done with Boxee 1.5 on linux or windows (or of course on the BoxeeBox)
#* However final testing should be done on the BoxeeBox as there are some differences to the windows/linux implementation
#
#\section Tests
#
