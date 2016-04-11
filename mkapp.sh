#!/bin/bash

#repository project dir has to be the same name as the source project dir
#eg. PlexForBoxee-beta

UDIR=${PWD##*/}
UPLOADDIR=${UDIR,,}
APPREPO="192.168.1.101"
APPPATH="/var/www/html/grantmcwilliams.com/${UPLOADDIR}"
TMPDIR=$(mktemp -d)
echo "Please enter PlexforBoxee app version"
read APPVERSION 
if [[ ! $APPVERSION =~ ^[0-9]\.[0-9][0-9]?$ ]] ;then
	echo "Not a proper version number"
	echo "Enter a number in the following format 1.5"
	exit 1
fi

yesno()
{
	echo -n "$1? <y|n> "
	read ANS
	while true ;do
		case $ANS in
			[yY] | [yY][Ee][Ss] ) return 0 ;;
			[nN] | [n|N][O|o] )   return 1 ;;
			*) echo "Invalid input"        ;;
		esac
	done
}

if [[ -d ./app-files ]] ;then
	if [[ -d ./app-files/plexee.plexforboxee ]] ;then
		rm -Rf app-files/plexee.plexforboxee  
	fi	
	cp -Rf plexee.plexforboxee app-files
	cd app-files
	if [[ -f plexee.plexforboxee/descriptor.xml ]] ;then
		sed "s/<version>[0-9]\.[0-9]*<\/version>/<version>${APPVERSION}<\/version>/g" plexee.plexforboxee/descriptor.xml > ${TMPDIR}/descriptor.xml
	fi	
	cat ${TMPDIR}/descriptor.xml
	if yesno "Does this look OK" ;then
		cat ${TMPDIR}/descriptor.xml > plexee.plexforboxee/descriptor.xml
	fi
	if [[ -f plexee.plexforboxee-${APPVERSION}.zip ]];then
		rm -f plexee.plexforboxee-${APPVERSION}.zip 
	fi
	zip -r "plexee.plexforboxee-${APPVERSION}.zip" plexee.plexforboxee
    if [[ -L plexee.plexforboxee-latest.zip ]];then
		unlink plexee.plexforboxee-latest.zip
	else
		rm -f plexee.plexforboxee-latest.zip
	fi

    ln -s plexee.plexforboxee-${APPVERSION}.zip plexee.plexforboxee-latest.zip
	echo "Upload and sign the zip file at http://bbx.boxee.tv/developer/appedit?appid=plexee.plexforboxee"
	echo "then download the signature file to $PWD and resume this script"
	read
	if [[ ! -f "plexee.plexforboxee-${APPVERSION}.zip.xml" ]] ;then
		echo "Unable to find signature file"
		echo "Download it to $PWD and resume this script"
		if [[ ! -f "plexee.plexforboxee-${APPVERSION}.zip.xml" ]] ;then
			echo "Unable to find signature file - exiting"
			exit 1
		fi
	fi	
	if ! scp plexee.plexforboxee-${APPVERSION}.zip* "root@${APPREPO}:${APPPATH}/download" ;then
		echo "Unable to upload plexee.plexforboxee-${APPVERSION}.zip and signature to ${APPREPO} - exiting"
		exit 1
	fi

	if ! ssh root@${APPREPO} "cd ${APPPATH}/download/; unlink plexee.plexforboxee-latest.zip; ln -s plexee.plexforboxee-${APPVERSION}.zip plexee.plexforboxee-latest.zip; chown -R apache.apache ${APPPATH}/; chmod -R 755 ${APPPATH}/; restorecon ${APPPATH}/" ;then
		echo "Unable to change permissions on ${APPPATH}"
	fi

	if [[ ! -e ./index.xml ]] ;then
		if ! scp root@${APPREPO}:${APPPATH}/index.xml ./index.xml ; then 
			echo "Unable to download ${APPPATH}/index.xml -exiting"
			exit 1
		fi
	fi
	
	sed -i "s/<version>[0-9]\.[0-9][0-9]*<\/version>/<version>${APPVERSION}<\/version>/g" ./index.xml 
	sed -i "s/(v. [0-9]\.[0-9][0-9]*)/(v. ${APPVERSION})/g" ./index.xml 
	if ! scp ./index.xml "root@${APPREPO}:${APPPATH}/" ; then 
		echo "Unable to upload new repository index - exiting"
		exit 1
	fi
fi
