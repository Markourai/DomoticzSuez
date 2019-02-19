# TODO
Add/change device to get the total water meter (and not only the daily consumption) 


# Plugin Suez for Domoticz

[Domoticz](https://domoticz.com) plugin which grab data from French water meter. It grabs data from [toutsurmoneau](https://www.toutsurmoneau.fr) user account and store them inside a counter device log.

## Installing

Copy the plugin.py to domoticz directory/plugins/DomoticzSuez or change directory to domoticz directory/plugins and issue the following command:

```
git clone https://github.com/Markourai/DomoticzSuez
```

To update, overwrite plugin.py or change directory to domoticz directory/plugins/DomoticzLinky and issue the following command:
```
git pull
```

Give the execution permission, for Linux:
```
chmod ugo+x plugin.py
```

Restart Domoticz.

## Configuration

Add the Suez hardware in Domoticz Settings / Hardware configuration tab, giving the e-mail address and password of your toutsurmoneau account. You can choose the number of days to collect data for the days log. 

After enabling the hardware, you shall have a new Suez Utility device and watch your energy consumption history with the Log button.

## Authors

* **Guillaume Zin** - *Port Linky to Domoticz plugin framework* - [DomoticzLinky](https://github.com/guillaumezin/DomoticzLinky)
* **Mar Kourai** - *Linky plugin modification for Suez * - [DomoticzSuez](https://github.com/Markourai/DomoticzSuez)

## License

This project is licensed under the GPLv3 license - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

* Guillaume Zin (for inspiration)
* Domoticz team
