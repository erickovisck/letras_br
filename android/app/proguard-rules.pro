# Proguard rules for LetrasBR Translator
-keepattributes *Annotation*
-keepclassmembers class * {
    @org.json.* <fields>;
    @org.json.* <methods>;
}
