import { FieldSchema } from "../fieldSchema.interface";

export const uiRegistrationSchema: FieldSchema = {
  schemaId:    "ui-registration",
  version:     "1.0.0",
  target:      "ui",
  description: "Customer registration form — full hierarchical schema example",

  goalCondition: {
    ui: {
      successSelector: ".success-message, .alert-success, [data-success]",
      successText:     "successfully",
      urlContains:     "/success",
      waitForSelector: "form",
    },
  },

  astarConfig: {
    maxIterations:    500,
    heuristicWeight:  1.0,
    goalTimeout:      30000,
    allowPartialGoal: false,
  },

  sections: [

    // ═══════════════════════════════════════════════════════
    // SECTION 1: Personal Info — Mandatory
    // ═══════════════════════════════════════════════════════
    {
      sectionName: "personalInfo",
      mandatory:   true,
      weight:      10,
      label:       "Personal Information",
      stepIndex:   0,
      fields: [
        {
          name:        "firstName",
          type:        "text",
          weight:      9,
          label:       "First Name",
          placeholder: "Enter your first name",
          selector:    '[name="firstName"], [id="firstName"], [placeholder*="first" i]',
          validationRule: {
            pattern:      "^[a-zA-Z]{2,50}$",
            minLength:    2,
            maxLength:    50,
            errorMessage: "First name: 2-50 alphabetic characters only",
          },
          dataHints: {
            validSamples:   ["Karthick", "Priya", "John", "Aisha"],
            invalidSamples: ["A", "123Name", ""],
          },
        },
        {
          name:        "lastName",
          type:        "text",
          weight:      9,
          label:       "Last Name",
          placeholder: "Enter your last name",
          selector:    '[name="lastName"], [id="lastName"], [placeholder*="last" i]',
          validationRule: {
            pattern:      "^[a-zA-Z]{2,50}$",
            minLength:    2,
            maxLength:    50,
            errorMessage: "Last name: 2-50 alphabetic characters only",
          },
          dataHints: {
            validSamples:   ["Kumar", "Smith", "Raj", "Chen"],
            invalidSamples: ["", "1", "A"],
          },
        },
        {
          name:        "email",
          type:        "email",
          weight:      10,
          label:       "Email Address",
          placeholder: "Enter your email address",
          selector:    '[name="email"], [type="email"], [id="email"]',
          validationRule: {
            pattern:      "^[\\w.-]+@[\\w.-]+\\.\\w{2,}$",
            errorMessage: "Please enter a valid email address",
          },
          dataHints: {
            validSamples:   ["test@astra.com", "user@example.com", "qa@freewheel.tv"],
            invalidSamples: ["notanemail", "missing@", "@nodomain"],
            format:         "email",
          },
        },
        {
          name:        "phone",
          type:        "phone",
          weight:      8,
          label:       "Mobile Number",
          placeholder: "Enter 10-digit mobile number",
          selector:    '[name="phone"], [type="tel"], [id="phone"]',
          validationRule: {
            pattern:      "^[6-9]\\d{9}$",
            errorMessage: "Enter a valid 10-digit Indian mobile number",
          },
          dataHints: {
            validSamples:   ["9876543210", "8123456789", "7001234567"],
            invalidSamples: ["12345", "0123456789", "abcdefghij"],
            locale:         "en-IN",
          },
        },
      ],
    },

    // ═══════════════════════════════════════════════════════
    // SECTION 2: Address — Mandatory
    // Nested children inherit mandatory: true
    // ═══════════════════════════════════════════════════════
    {
      sectionName: "address",
      mandatory:   true,
      weight:      8,
      label:       "Address Details",
      stepIndex:   0,
      fields: [
        {
          name:     "addressBlock",
          type:     "text",
          weight:   8,
          label:    "Address",
          selector: "[data-section='address'], fieldset.address",
          children: [
            {
              name:        "street",
              type:        "text",
              weight:      8,
              label:       "Street / Area",
              placeholder: "Enter street name or area",
              selector:    '[name="street"], [name="address1"], [id="street"]',
              validationRule: {
                minLength:    3,
                maxLength:    100,
                errorMessage: "Street address is required",
              },
              dataHints: {
                validSamples:   ["12 Main Street", "45 Gandhi Road", "Plot 7 Lake View"],
                invalidSamples: ["", "A"],
              },
            },
            {
              name:        "city",
              type:        "text",
              weight:      8,
              label:       "City",
              placeholder: "Enter city name",
              selector:    '[name="city"], [id="city"]',
              validationRule: {
                pattern:      "^[a-zA-Z\\s]{2,50}$",
                errorMessage: "Enter a valid city name",
              },
              dataHints: {
                validSamples:   ["Chennai", "Bangalore", "Mumbai", "Hyderabad"],
                invalidSamples: ["", "12345"],
              },
            },
            {
              name:        "state",
              type:        "dropdown",
              weight:      7,
              label:       "State",
              selector:    'select[name="state"], [id="state"]',
              validValues: [
                "Tamil Nadu", "Karnataka", "Maharashtra",
                "Delhi", "Telangana", "Kerala",
              ],
              dataHints: {
                validSamples: ["Tamil Nadu", "Karnataka"],
              },
            },
            {
              name:        "pincode",
              type:        "number",
              weight:      7,
              label:       "Pincode",
              placeholder: "Enter 6-digit pincode",
              selector:    '[name="pincode"], [name="zipcode"], [id="pincode"]',
              validationRule: {
                pattern:      "^[1-9][0-9]{5}$",
                errorMessage: "Enter a valid 6-digit pincode",
              },
              dataHints: {
                validSamples:   ["600001", "560001", "400001"],
                invalidSamples: ["12345", "000000", "abcdef"],
              },
            },
          ],
        },
      ],
    },

    // ═══════════════════════════════════════════════════════
    // SECTION 3: Credentials — Mandatory | Step 2
    // ═══════════════════════════════════════════════════════
    {
      sectionName: "credentials",
      mandatory:   true,
      weight:      10,
      label:       "Login Credentials",
      stepIndex:   1,
      fields: [
        {
          name:        "username",
          type:        "text",
          weight:      10,
          label:       "Username",
          placeholder: "Choose a username",
          selector:    '[name="username"], [id="username"]',
          validationRule: {
            pattern:      "^[a-zA-Z0-9_]{4,20}$",
            minLength:    4,
            maxLength:    20,
            errorMessage: "Username: 4-20 alphanumeric characters or underscore",
          },
          dataHints: {
            validSamples:   ["astra_user", "test_qa_01", "karthick_001"],
            invalidSamples: ["ab", "user name", "a".repeat(21)],
            unique:         true,
          },
        },
        {
          name:        "password",
          type:        "password",
          weight:      10,
          label:       "Password",
          placeholder: "Create a strong password",
          selector:    '[name="password"], [id="password"]',
          validationRule: {
            pattern:      "^(?=.*[A-Z])(?=.*\\d)(?=.*[@$!%*?&])[A-Za-z\\d@$!%*?&]{8,}$",
            minLength:    8,
            errorMessage: "Min 8 chars with 1 uppercase, 1 number, 1 special char",
          },
          dataHints: {
            validSamples:   ["Test@1234", "Secure#Pass9", "Astra@2024!"],
            invalidSamples: ["weak", "12345678", "NoSpecial1"],
          },
        },
        {
          name:        "confirmPassword",
          type:        "password",
          weight:      10,
          label:       "Confirm Password",
          placeholder: "Re-enter your password",
          selector:    '[name="confirmPassword"], [name="confirm_password"]',
          dependencies: [
            {
              dependsOn: "password",
              whenValue: "",
              operator:  "notEquals",
            },
          ],
          validationRule: {
            errorMessage: "Passwords must match",
          },
          dataHints: {
            validSamples: ["Test@1234"],
          },
        },
      ],
    },

    // ═══════════════════════════════════════════════════════
    // SECTION 4: Preferences — Optional
    // A* skips this entire section
    // ═══════════════════════════════════════════════════════
    {
      sectionName: "preferences",
      mandatory:   false,
      weight:      3,
      label:       "Preferences (Optional)",
      stepIndex:   1,
      fields: [
        {
          name:        "gender",
          type:        "dropdown",
          weight:      3,
          label:       "Gender",
          selector:    'select[name="gender"], [id="gender"]',
          validValues: ["Male", "Female", "Non-binary", "Prefer not to say"],
          dataHints: {
            validSamples: ["Male", "Female"],
          },
        },
        {
          name:        "dateOfBirth",
          type:        "date",
          weight:      3,
          label:       "Date of Birth",
          placeholder: "YYYY-MM-DD",
          selector:    '[name="dateOfBirth"], [name="dob"], [id="dateOfBirth"]',
          dataHints: {
            validSamples: ["1995-06-15", "2000-01-01"],
            format:       "YYYY-MM-DD",
          },
        },
        {
          name:     "newsletterOptIn",
          type:     "checkbox",
          weight:   2,
          label:    "Subscribe to Newsletter",
          selector: '[name="newsletter"], [id="newsletterOptIn"]',
          validValues: ["true", "false"],
          dataHints: {
            validSamples:   ["true"],
            invalidSamples: ["false"],
          },
        },
      ],
    },

  ],
};