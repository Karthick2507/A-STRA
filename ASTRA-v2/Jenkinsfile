// ASTRA-v2 Jenkins Pipeline
// Supports parameterised runs: ENV, BROWSER, SUITE, NOTIFY

pipeline {
    agent any

    parameters {
        choice(name: 'ENV',     choices: ['staging', 'dev', 'prod'],        description: 'Target environment')
        choice(name: 'BROWSER', choices: ['chromium', 'firefox', 'webkit'], description: 'Browser for UI tests')
        choice(name: 'SUITE',   choices: ['smoke', 'regression', 'all'],    description: 'Test suite to run')
        booleanParam(name: 'NOTIFY', defaultValue: true, description: 'Send Slack/Teams/Email notification')
    }

    environment {
        ASTRA_ENV     = "${params.ENV}"
        PYTHON        = 'python3'
        VENV_DIR      = '.venv'
        WORK_DIR      = 'ASTRA-v2'
        API_TOKEN     = credentials('astra-api-token')
        SLACK_WEBHOOK = credentials('slack-webhook-url')
    }

    options {
        timestamps()
        timeout(time: 60, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Setup Python') {
            steps {
                dir(WORK_DIR) {
                    sh '''
                        ${PYTHON} -m venv ${VENV_DIR}
                        . ${VENV_DIR}/bin/activate
                        pip install --upgrade pip
                        pip install -r requirements.txt
                        playwright install --with-deps ${BROWSER}
                    '''
                }
            }
        }

        stage('Lint') {
            steps {
                dir(WORK_DIR) {
                    sh '''
                        . ${VENV_DIR}/bin/activate
                        pip install ruff --quiet
                        ruff check . --select E,F,W --ignore E501 || true
                    '''
                }
            }
        }

        stage('UI Tests') {
            when { expression { params.SUITE != 'api' } }
            steps {
                dir(WORK_DIR) {
                    sh '''
                        . ${VENV_DIR}/bin/activate
                        pytest UI/tests \
                            -m "${SUITE}" \
                            --browser=${BROWSER} \
                            --alluredir=Data/allure-results \
                            -n auto \
                            --tb=short \
                            -q \
                            || true
                    '''
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'ASTRA-v2/Data/allure-results/**', allowEmptyArchive: true
                    archiveArtifacts artifacts: 'ASTRA-v2/Data/screenshots/**',    allowEmptyArchive: true
                    archiveArtifacts artifacts: 'ASTRA-v2/Data/traces/**',         allowEmptyArchive: true
                }
            }
        }

        stage('API Tests') {
            steps {
                dir(WORK_DIR) {
                    sh '''
                        . ${VENV_DIR}/bin/activate
                        pytest API/tests \
                            --alluredir=Data/allure-results \
                            -n auto \
                            --tb=short \
                            -q \
                            || true
                    '''
                }
            }
        }

        stage('Allure Report') {
            steps {
                allure([
                    includeProperties: false,
                    jdk: '',
                    properties: [],
                    reportBuildPolicy: 'ALWAYS',
                    results: [[path: "${WORK_DIR}/Data/allure-results"]]
                ])
            }
        }
    }

    post {
        always {
            echo "Pipeline complete — ${currentBuild.result}"
        }
        failure {
            script {
                if (params.NOTIFY && env.SLACK_WEBHOOK) {
                    slackSend(
                        channel: '#astra-ci',
                        color: 'danger',
                        message: "ASTRA FAILED — ${env.JOB_NAME} #${env.BUILD_NUMBER} env=${params.ENV} ${env.BUILD_URL}"
                    )
                }
            }
        }
        success {
            script {
                if (params.NOTIFY && env.SLACK_WEBHOOK) {
                    slackSend(
                        channel: '#astra-ci',
                        color: 'good',
                        message: "ASTRA PASSED — ${env.JOB_NAME} #${env.BUILD_NUMBER} env=${params.ENV} ${env.BUILD_URL}"
                    )
                }
            }
        }
        cleanup {
            cleanWs()
        }
    }
}
