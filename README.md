# Smart Energy Metering and Automated Credit Recharge System

## Project Summary

A smart energy metering and automated credit recharge system designed to streamline electricity consumption monitoring, credit management, payment processing, and real-time power control. The system connects a web/mobile client, a Django-based backend, a Neon-hosted PostgreSQL database, payment gateways, and IoT meter hardware to monitor energy usage and automatically control power supply based on the user's available credit balance.

The system enables consumers to view real-time energy telemetry, purchase electricity credit, monitor consumption, receive alerts, and track transaction history. On the hardware side, the meter continuously reports energy readings to the backend while automatically switching the power relay ON or OFF based on the user's credit status.

## Project Goals

* **Automated Meter Actuation:** Automatically switch the meter relay ON or OFF based on the user's available credit without requiring manual intervention.
* **Secure Financial Workflows:** Process recharge transactions securely through a payment gateway with server-side verification, webhook validation, and idempotent transaction handling.
* **Low-Latency Synchronization:** Maintain near real-time communication between the Django backend and IoT meter hardware for telemetry updates and relay state changes.
* **Energy Visibility & Analytics:** Provide consumers with real-time consumption information, historical usage analytics, low-credit alerts, and transaction records.
* **Reliable Credit Management:** Accurately calculate credit depletion from meter readings and automatically enforce power availability when credit reaches its configured threshold.

## Core Application Features

### 1. Authentication & User Management

* User registration and login
* Secure authentication and authorization
* User profile management
* Meter registration and user-to-meter linking
* Management of notification preferences

### 2. Main Dashboard & Real-Time Telemetry

* Current credit balance
* Meter online/offline status
* Relay state
* Line voltage
* Current consumption
* Active power
* Energy consumption
* Last meter communication timestamp

### 3. Energy Analytics

* Historical energy consumption data
* Daily, weekly, and monthly consumption aggregation
* Consumption trends and graphs
* Credit usage analysis
* Estimated remaining credit/runtime

### 4. Credit & Relay Management

* Real-time credit balance tracking
* Automatic credit depletion based on meter readings
* Configurable low-credit thresholds
* Automatic power disconnection when credit is exhausted
* Automatic power restoration after successful recharge
* Manual relay control where authorized

### 5. Recharge & Payment Processing

* Recharge amount selection
* Payment gateway checkout initialization
* Checkout reference generation
* Payment gateway redirection
* Secure webhook processing
* Server-side payment verification
* Idempotent transaction processing
* Automatic credit fulfillment after successful payment

### 6. Transaction History

* Recharge records
* Transaction references
* Recharge amounts
* Payment methods
* Transaction timestamps
* Payment and fulfillment statuses
* Complete transaction audit trail

### 7. Notifications & Alerts

* Low-credit notifications
* Recharge confirmation
* Power disconnection alerts
* Power restoration notifications
* Meter offline alerts
* Failed payment notifications

### 8. Profile & Settings

* User information management
* Registered meter management
* Notification preferences
* Security settings
* Account configuration

## System Architecture

The system consists of four primary layers:

**Client Application → Django Backend → Neon PostgreSQL → IoT Meter**

The client application communicates with the Django REST API for authentication, meter information, credit management, payments, analytics, and transaction history.

The Django backend serves as the central business-logic layer. It handles authentication, payment processing, credit calculations, transaction management, telemetry ingestion, relay commands, and communication with the IoT devices.

**Neon PostgreSQL** serves as the primary persistent database for users, meters, telemetry, credit balances, transactions, relay states, and system events.

IoT meters communicate with the Django backend through an appropriate device communication protocol such as **MQTT, HTTP, or WebSockets**, depending on the final hardware and networking architecture.

## Current Progress

### System Architecture & Data Flow

* Defined the end-to-end system architecture connecting the client, Django backend, PostgreSQL database, payment gateway, and IoT hardware.
* Defined the major application workflows for authentication, recharge, credit fulfillment, telemetry collection, and relay control.

### Backend Foundation

* Django backend architecture established.
* PostgreSQL selected as the primary database, hosted through Neon.
* Backend responsibilities identified for authentication, payments, credit management, telemetry processing, and hardware communication.

### Payment Workflow

* Designed the recharge flow from client-side payment initiation through payment gateway processing and backend webhook verification.
* Defined the requirement for server-side payment verification and idempotent transaction handling.
* Designed the workflow for automatically increasing a user's electricity credit after successful payment.

## Remaining Development Work

### 1. Django Backend & Infrastructure

* Implement authentication and authorization APIs.
* Design and implement PostgreSQL database models.
* Implement meter registration and user-meter linking.
* Implement payment gateway initialization endpoints.
* Implement payment verification and webhook endpoints.
* Add webhook signature/HMAC validation where supported by the payment provider.
* Implement idempotency protection for payment transactions.
* Implement credit balance management.
* Implement credit depletion calculations.
* Implement telemetry ingestion endpoints.
* Implement relay command endpoints.
* Implement background workers or scheduled jobs for credit and meter processing.
* Implement API rate limiting and security controls.
* Implement logging and audit trails.

### 2. Neon PostgreSQL Database

Core entities are expected to include:

* Users
* Meters
* Meter telemetry
* Credit accounts/balances
* Recharge transactions
* Payment records
* Relay states/commands
* Meter events
* Notifications
* System audit logs

The database should maintain transactional consistency between successful payments, credit updates, and transaction records.

### 3. Client Application

* Build authentication screens.
* Build meter registration/linking flow.
* Develop the main dashboard.
* Display real-time telemetry.
* Display current credit balance and relay status.
* Implement energy consumption charts.
* Implement recharge flow.
* Integrate payment checkout.
* Implement transaction history.
* Implement notification interfaces.
* Build profile and settings pages.

### 4. Real-Time Communication

Implement a communication mechanism between the Django backend and IoT meters using **MQTT, WebSockets, or HTTP**, depending on the final hardware architecture.

The communication layer should support:

* Telemetry transmission from meter to backend
* Relay commands from backend to meter
* Credit/balance synchronization
* Meter heartbeat/online status
* Command acknowledgements
* Device authentication
* Automatic reconnection handling

### 5. IoT Meter Hardware & Firmware

Using an **ESP32/ESP8266 or similar microcontroller**:

* Connect the meter to the network.
* Authenticate the device with the backend.
* Read voltage, current, power, and energy consumption.
* Periodically transmit telemetry to Django.
* Receive relay commands from the backend.
* Switch the relay based on the received command.
* Detect loss of network connectivity.
* Maintain appropriate local fail-safe behavior.
* Send periodic heartbeat signals.
* Acknowledge relay commands.
* Synchronize credit/relay state with the backend.

### 6. Automated Credit & Power Control

The core control loop will operate approximately as follows:

**Meter measures consumption → IoT device sends telemetry → Django processes reading → credit balance is calculated → system evaluates credit status → relay command is issued → meter switches power ON/OFF → updated state is recorded.**

When a user successfully recharges:

**Client initiates payment → payment gateway processes transaction → Django receives webhook → payment is verified → transaction is marked successful → credit balance is increased → relay restoration command is sent to the meter → meter restores power.**

When credit is exhausted:

**Meter reports consumption → Django updates credit → balance reaches threshold → system marks account as depleted → relay OFF command is sent → meter disconnects power → user receives notification.**

## Target Technology Stack

| Layer                   | Technology                                  |
| ----------------------- | ------------------------------------------- |
| Backend                 | Django / Django REST Framework              |
| Database                | PostgreSQL                                  |
| Database Hosting        | Neon                                        |
| Authentication          | Django REST authentication / JWT            |
| Payments                | Paystack / Flutterwave / Stripe             |
| Real-Time Communication | MQTT / WebSockets / HTTP                    |
| Background Processing   | Celery + Redis or Django background workers |
| IoT Hardware            | ESP32 / ESP8266                             |
| Frontend                | Web or Mobile Client                        |
| Notifications           | Push notification service / Email / SMS     |
| Deployment              | Cloud-hosted Django application             |

## Expected Outcome

The completed system will provide an end-to-end smart electricity management platform where users can **monitor energy consumption, purchase electricity credit, receive real-time alerts, and automatically control their power supply**.

The Django backend will serve as the central control and business-logic layer, Neon PostgreSQL will provide reliable persistent storage, and IoT-enabled meters will provide real-time energy telemetry and physical relay actuation.
