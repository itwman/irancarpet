import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// کلید امضا بیرون از مخزن نگه داشته می‌شود (android/key.properties)
val keyProps = Properties().apply {
    val f = rootProject.file("key.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}
// فرشستان کلید امضای خودش را دارد (android/key-farshestan.properties)
val fsKeyProps = Properties().apply {
    val f = rootProject.file("key-farshestan.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}

android {
    namespace = "net.irancarpet.app"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        isCoreLibraryDesugaringEnabled = true
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "net.irancarpet.app"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildFeatures {
        resValues = true
    }

    // سه اپ از یک کد: «ایران کارپت» (فروشگاه)، «فرش‌یاب» (پیدا کردن فرش بر اساس نیاز) و «فرشستان»
    signingConfigs {
        create("release") {
            if (keyProps.isNotEmpty()) {
                storeFile = file(keyProps.getProperty("storeFile"))
                storePassword = keyProps.getProperty("storePassword")
                keyAlias = keyProps.getProperty("keyAlias")
                keyPassword = keyProps.getProperty("keyPassword")
            }
        }
        create("farshestan") {
            if (fsKeyProps.isNotEmpty()) {
                storeFile = file(fsKeyProps.getProperty("storeFile"))
                storePassword = fsKeyProps.getProperty("storePassword")
                keyAlias = fsKeyProps.getProperty("keyAlias")
                keyPassword = fsKeyProps.getProperty("keyPassword")
            }
        }
    }

    flavorDimensions += "app"
    productFlavors {
        create("store") {
            dimension = "app"
            applicationId = "net.irancarpet.app"
            resValue("string", "app_name", "ایران کارپت")
            manifestPlaceholders["appScheme"] = "irancarpet"
            signingConfig = if (keyProps.isNotEmpty()) signingConfigs.getByName("release") else signingConfigs.getByName("debug")
        }
        create("finder") {
            dimension = "app"
            applicationId = "net.irancarpet.finder"
            resValue("string", "app_name", "فرش‌یاب")
            manifestPlaceholders["appScheme"] = "farshyab"
            signingConfig = if (keyProps.isNotEmpty()) signingConfigs.getByName("release") else signingConfigs.getByName("debug")
        }
        // فرشستان: همان کد، ظاهر «خانهٔ ایرانی» (با --dart-define=APP=farshestan بسازید)
        create("farshestan") {
            dimension = "app"
            applicationId = "ir.farshestan.app"
            resValue("string", "app_name", "فرشستان")
            manifestPlaceholders["appScheme"] = "farshestan"
            signingConfig = if (fsKeyProps.isNotEmpty()) signingConfigs.getByName("farshestan") else signingConfigs.getByName("debug")
        }
    }

    buildTypes {
        release {
            // امضا از هر flavor می‌آید (ایران کارپت و فرش‌یاب: key.properties؛ فرشستان: key-farshestan.properties)
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.5")
}
